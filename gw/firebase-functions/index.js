/**
 * GW eSports — Firebase RTDB server-side deposit verification.
 *
 * Trigger: depositRequests/{id} create
 * 1. Reads paymentId from the request (written by user-panel after Razorpay checkout)
 * 2. Verifies the payment against Razorpay REST API (status=captured, amount matches)
 * 3. Credits users/{uid}/wallet/deposit (+ depositBalance, coins) atomically
 * 4. Marks deposits/{depositId} approved and the request as credited
 *
 * Setup:
 *   firebase functions:config:set razorpay.key_secret="YOUR_KEY_SECRET"
 *   (key_id is public; it lives at RTDB settings/razorpayKeyId, set from admin panel)
 *   firebase deploy --only functions
 */
const functions = require('firebase-functions');
const admin = require('firebase-admin');
const https = require('https');

admin.initializeApp();

function rzpGetPayment(keyId, keySecret, paymentId) {
  return new Promise((resolve, reject) => {
    const auth = Buffer.from(keyId + ':' + keySecret).toString('base64');
    const opts = {
      hostname: 'api.razorpay.com',
      path: '/v1/payments/' + encodeURIComponent(paymentId),
      method: 'GET',
      headers: { Authorization: 'Basic ' + auth }
    };
    const req = https.request(opts, res => {
      let body = '';
      res.on('data', d => { body += d; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(body);
          if (res.statusCode >= 200 && res.statusCode < 300) resolve(parsed);
          else reject(new Error(parsed.error && parsed.error.description || 'Razorpay API error ' + res.statusCode));
        } catch (e) { reject(e); }
      });
    });
    req.on('error', reject);
    req.setTimeout(10000, () => req.destroy(new Error('Razorpay API timeout')));
    req.end();
  });
}

exports.verifyRazorpayDeposit = functions.database.ref('depositRequests/{reqId}')
  .onCreate(async (snapshot, context) => {
    const req = snapshot.val() || {};
    const reqRef = snapshot.ref;
    const depositId = req.depositId || ('dep_' + context.params.reqId);
    const uid = req.uid;
    const amount = Number(req.amount) || 0;
    const paymentId = req.paymentId || '';

    if (!uid || !paymentId || amount < 50) {
      await reqRef.update({ status: 'invalid', note: 'Missing uid/paymentId or amount < 50' });
      return null;
    }

    const keySecret = (functions.config().razorpay || {}).key_secret;
    const keyIdSnap = await admin.database().ref('settings/razorpayKeyId').once('value');
    const keyId = keyIdSnap.val();

    if (!keyId || !keySecret) {
      await reqRef.update({ status: 'awaiting_credentials', note: 'Razorpay credentials missing — admin approval se credit hoga' });
      return null;
    }

    await reqRef.update({ status: 'verifying' });

    let payment;
    try {
      payment = await rzpGetPayment(keyId, keySecret, paymentId);
    } catch (err) {
      await reqRef.update({ status: 'verify_failed', note: String(err.message || err) });
      return null;
    }

    if (!payment || payment.status !== 'captured' || Number(payment.amount) !== amount * 100 || payment.currency !== 'INR') {
      await reqRef.update({
        status: 'rejected',
        note: 'Payment not captured or amount mismatch (status=' + (payment && payment.status) + ')'
      });
      await admin.database().ref('deposits/' + depositId).update({
        status: 'rejected',
        note: 'Razorpay verification failed',
        processedAt: Date.now()
      });
      return null;
    }

    // Idempotency: never double-credit
    const flagRef = admin.database().ref('creditedPayments/' + paymentId);
    const flagRes = await flagRef.transaction(cur => {
      if (cur) return; // already credited
      return { uid: uid, amount: amount, depositId: depositId, creditedAt: Date.now() };
    });
    if (!flagRes.committed) {
      await reqRef.update({ status: 'already_credited', note: 'Duplicate webhook/request blocked' });
      return null;
    }

    const userRef = admin.database().ref('users/' + uid);
    await userRef.child('wallet/deposit').transaction(v => (Number(v) || 0) + amount);
    await userRef.child('depositBalance').transaction(v => (Number(v) || 0) + amount);
    await userRef.child('coins').transaction(v => (Number(v) || 0) + amount);

    await admin.database().ref('deposits/' + depositId).update({
      status: 'approved',
      txnId: paymentId,
      paymentId: paymentId,
      method: 'razorpay',
      verifiedByServer: true,
      processedAt: Date.now()
    });

    await admin.database().ref('transactions/DEP_' + depositId).transaction(cur => {
      if (cur) return;
      return {
        uid: uid,
        username: req.username || '',
        type: 'deposit',
        wallet: 'deposit',
        amount: amount,
        bonus: 0,
        note: 'Razorpay payment verified ' + paymentId,
        depositId: depositId,
        createdAt: Date.now(),
        uniqueId: 'DEP_' + depositId
      };
    });

    await reqRef.update({ status: 'credited', creditedAt: Date.now() });
    return null;
  });
