# GW eSports — Firebase Server (Razorpay Deposit Verification)

Firebase RTDB + Cloud Functions hi server hai. Client (user-panel.html) sirf payment karta hai aur
`depositRequests/{id}` likhta hai — **coins sirf server (Cloud Function) credit karta hai**, client se kabhi nahi.

## Kaise kaam karta hai
1. User deposit karta hai → Razorpay checkout → payment ID milta hai
2. user-panel likhta hai: `depositRequests/{id}` (uid, amount, paymentId) + `deposits/{id}` (status: pending)
3. **Cloud Function trigger hota hai** → Razorpay API se payment verify (captured + amount match)
4. Verify hone par: `users/{uid}/wallet/deposit` credit (transaction, double-credit protected) +
   `deposits/{id}` approved + `transactions/` record
5. User ka coin chip live update ho jata hai (RTDB watch)

Function deploy nahi hai to deposit `pending` rehta hai → admin panel se manually approve (purana flow).

## Deploy steps (ek baar karna hai)

```bash
# 1. Firebase CLI install + login
npm install -g firebase-tools
firebase login

# 2. Is folder mein jao
cd firebase-functions

# 3. Firebase project select karo
firebase use gw-esports-559b3

# 4. Razorpay KEY SECRET set karo (Dashboard → Settings → API Keys → Key Secret)
firebase functions:config:set razorpay.key_secret="YOUR_KEY_SECRET"

# 5. Deploy
firebase deploy --only functions
```

⚠️ **Blaze (pay-as-you-go) plan chahiye** Cloud Functions ke liye — Firebase Console → Upgrade.
RTDB trigger free tier mein bhi bahut sasta hai (5 users ke app ke liye practically ₹0).

## Razorpay Key ID (public wala)
Admin panel → **RZP Key** button → Key ID daalo (`rzp_test_xxx`). Ye checkout ke liye chahiye —
ye public hota hai, secret NAHI. Secret sirf step 4 mein CLI config mein jata hai.

## Security notes
- `settings/razorpayKeyId` public read hai (checkout ke liye zaroori) — ye key ID hai, secret nahi
- Key secret sirf Cloud Function config mein rehta hai — database/browser mein kabhi nahi
- `creditedPayments/{paymentId}` idempotency flag — same payment do baar credit nahi ho sakta
- Wallet paths pe client-side write ab sirf in 3 jagah se hota hai: withdraw (escrow), join (entry fee),
  aur admin approve — Razorpay deposit credit 100% server-side
