package com.gwesports.app;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.webkit.WebSettings;
import android.webkit.WebView;
import org.json.JSONObject;

public class MainActivity extends Activity implements com.razorpay.PaymentResultListener {
    private WebView web;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        web = new WebView(this);
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setJavaScriptCanOpenWindowsAutomatically(true);
        s.setSupportMultipleWindows(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setTextZoom(100);
        s.setInitialScale(0);

        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true);

        web.setWebViewClient(new GWWebViewClient());
        web.setWebChromeClient(new GWWebChromeClient());
        web.addJavascriptInterface(new GWPaymentBridge(this), "GWAndroid");
        try {
            com.razorpay.Checkout.preload(getApplicationContext());
        } catch (Exception ignored) {
        }
        web.loadUrl(getString(R.string.app_url));
    }

    void onNativePayResult(final boolean ok, final String data) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                if (web == null) return;
                try {
                    String payload = ok
                            ? "{ok:true,paymentId:" + JSONObject.quote(data == null ? "" : data) + "}"
                            : "{ok:false,error:" + JSONObject.quote(data == null ? "" : data) + "}";
                    web.evaluateJavascript("window.__gwNativePayResult&&window.__gwNativePayResult(" + payload + ")", null);
                } catch (Exception ignored) {
                }
            }
        });
    }

    @Override
    public void onPaymentSuccess(String razorpayPaymentId) {
        onNativePayResult(true, razorpayPaymentId == null ? "" : razorpayPaymentId);
    }

    @Override
    public void onPaymentError(int code, String response) {
        onNativePayResult(false, "Error code " + code + ": " + (response == null ? "" : response));
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }
}
