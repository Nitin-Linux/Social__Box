/**
 * GW eSports — Razorpay Deposit Verifier (FREE server via Google Apps Script)
 *
 * Ye script hi "server" hai: browser paymentId bhejta hai, ye Razorpay API se
 * payment verify karta hai (captured + amount match), phir Firebase RTDB mein
 * wallet credit karta hai. Key Secret sirf yahan rehta hai — browser mein kabhi nahi.
 *
 * SETUP:
 * 1. Neeche 3 constants apne values se bharo
 * 2. script.google.com → New Project → ye poora code paste karo
 * 3. Deploy → New deployment → Type: Web app
 *    - Execute as: Me
 *    - Who has access: Anyone
 * 4. Jo /exec URL mile wo copy karo
 * 5. Admin panel → "Verify URL" button → wo URL paste karke save
 */
const RZP_KEY_ID = 'rzp_test_APNI_KEY_ID';
const RZP_KEY_SECRET = 'APNA_KEY_SECRET';
const DB_URL = 'https://gw-esports-559b3-default-rtdb.asia-southeast1.firebasedatabase.app';

function doPost(e) {
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const paymentId = String(body.paymentId || '');
    const depositId = String(body.depositId || '');
    if (!paymentId) return json({ ok: false, error: 'paymentId missing' });

    // Double-credit protection
    if (rtdbGet('creditedPayments/' + paymentId)) {
      return json({ ok: true, already: true });
    }

    // Razorpay se payment verify karo
    const pay = rzpGet('/payments/' + paymentId);
    if (!pay || pay.status !== 'captured') {
      return json({ ok: false, error: 'payment not captured (status: ' + (pay && pay.status) + ')' });
    }
    if (pay.currency !== 'INR') {
      return json({ ok: false, error: 'currency mismatch' });
    }
    const amount = pay.amount / 100;
    if (amount < 50) {
      return json({ ok: false, error: 'amount < 50' });
    }

    // Deposit request dhundo (paymentId se match)
    const reqs = rtdbGet('depositRequests') || {};
    let reqId = null, req = null;
    for (const k in reqs) {
      if (reqs[k] && reqs[k].paymentId === paymentId) { reqId = k; req = reqs[k]; break; }
    }
    if (!req || !req.uid) {
      return json({ ok: false, error: 'deposit request not found' });
    }
    const uid = String(req.uid);

    // Wallet credit (jo amount Razorpay ne li, WAHI credit hoga)
    const cur = Number(rtdbGet('users/' + uid + '/wallet/deposit') || 0);
    const nd = cur + amount;
    rtdbPatch('users/' + uid, { wallet: { deposit: nd }, depositBalance: nd, coins: nd });

    // Records update
    rtdbPut('creditedPayments/' + paymentId, { uid: uid, amount: amount, depositId: depositId, at: Date.now() });
    if (depositId) {
      rtdbPatch('deposits/' + depositId, {
        status: 'approved', txnId: paymentId, paymentId: paymentId,
        method: 'razorpay', verifiedByServer: true, processedAt: Date.now()
      });
    }
    rtdbPatch('depositRequests/' + reqId, { status: 'credited', creditedAt: Date.now() });
    rtdbPost('transactions', {
      uid: uid, username: req.username || '', type: 'deposit', wallet: 'deposit',
      amount: amount, bonus: 0, note: 'Razorpay verified ' + paymentId,
      depositId: depositId, createdAt: Date.now(), uniqueId: 'DEP_' + (depositId || paymentId)
    });

    return json({ ok: true, credited: amount });
  } catch (err) {
    return json({ ok: false, error: String(err) });
  }
}

function rzpGet(path) {
  const res = UrlFetchApp.fetch('https://api.razorpay.com/v1' + path, {
    method: 'get',
    headers: { Authorization: 'Basic ' + Utilities.base64Encode(RZP_KEY_ID + ':' + RZP_KEY_SECRET) },
    muteHttpExceptions: true
  });
  return JSON.parse(res.getContentText());
}
function rtdbGet(path) {
  const res = UrlFetchApp.fetch(DB_URL + '/' + path + '.json', { muteHttpExceptions: true });
  const txt = res.getContentText();
  return txt === 'null' ? null : JSON.parse(txt);
}
function rtdbPatch(path, obj) {
  UrlFetchApp.fetch(DB_URL + '/' + path + '.json', { method: 'patch', payload: JSON.stringify(obj), muteHttpExceptions: true });
}
function rtdbPut(path, obj) {
  UrlFetchApp.fetch(DB_URL + '/' + path + '.json', { method: 'put', payload: JSON.stringify(obj), muteHttpExceptions: true });
}
function rtdbPost(path, obj) {
  UrlFetchApp.fetch(DB_URL + '/' + path + '.json', { method: 'post', payload: JSON.stringify(obj), muteHttpExceptions: true });
}
function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
