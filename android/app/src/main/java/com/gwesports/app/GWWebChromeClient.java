package com.gwesports.app;

import android.app.Dialog;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class GWWebChromeClient extends WebChromeClient {
    private Dialog popupDialog;

    @Override
    public boolean onCreateWindow(WebView view, boolean isDialog, boolean isUserGesture, Message resultMsg) {
        WebView popup = new WebView(view.getContext());
        WebSettings s = popup.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setJavaScriptCanOpenWindowsAutomatically(true);
        s.setSupportMultipleWindows(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(popup, true);
        popup.setWebViewClient(new WebViewClient());
        popup.setWebChromeClient(this);

        Dialog d = new Dialog(view.getContext());
        popupDialog = d;
        d.setContentView(popup);
        d.getWindow().setLayout(-1, -1);
        d.setCanceledOnTouchOutside(true);
        d.show();

        ((WebView.WebViewTransport) resultMsg.obj).setWebView(popup);
        resultMsg.sendToTarget();
        return true;
    }

    @Override
    public void onCloseWindow(WebView window) {
        if (popupDialog != null) {
            try {
                popupDialog.dismiss();
            } catch (Exception ignored) {
            }
            popupDialog = null;
        }
        super.onCloseWindow(window);
    }
}
