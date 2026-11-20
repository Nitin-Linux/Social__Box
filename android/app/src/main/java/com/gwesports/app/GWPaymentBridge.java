package com.gwesports.app;

import android.app.Activity;
import android.webkit.JavascriptInterface;
import org.json.JSONObject;

public class GWPaymentBridge {
    private final Activity activity;

    public GWPaymentBridge(Activity activity) {
        this.activity = activity;
    }

    @JavascriptInterface
    public boolean isAvailable() {
        return true;
    }

    @JavascriptInterface
    public String pay(final String json) {
        try {
            final JSONObject o = new JSONObject(json == null ? "{}" : json);
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    try {
                        com.razorpay.Checkout checkout = new com.razorpay.Checkout();
                        checkout.setKeyID(o.optString("key", "rzp_test_Tb3OlZbRcUJczq"));
                        JSONObject options = new JSONObject();
                        options.put("name", o.optString("name", "GW eSports"));
                        options.put("description", o.optString("description", "Deposit"));
                        String image = o.optString("image", "");
                        if (image.length() > 0) options.put("image", image);
                        options.put("currency", "INR");
                        options.put("amount", String.valueOf(o.optLong("amount", 0) * 100));
                        options.put("theme.color", "#e10111");
                        checkout.open(activity, options);
                    } catch (Exception e) {
                        ((MainActivity) activity).onNativePayResult(false, "checkout error: " + e.getMessage());
                    }
                }
            });
            return "ok";
        } catch (Exception e) {
            return "error: " + e.getMessage();
        }
    }
}
