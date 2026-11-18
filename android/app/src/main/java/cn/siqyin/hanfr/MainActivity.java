package cn.siqyin.hanfr;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * 漢法辭典 Android 外殼
 *
 * 為什麼用原生 WebView 而不是 Capacitor：
 *   Capacitor 會引入 node 依賴與 gradle 插件，CI 構建更重、更容易在
 *   runner 上出問題（漢維曾在 setup-android@v3 上反覆失敗）。
 *   本專案只需要載入 assets/www，原生殼足夠且穩定。
 */
public class MainActivity extends android.app.Activity {

    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        setContentView(webView);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);          // localStorage：語言/主題/記錄
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setTextZoom(100);                    // 不隨系統字號縮放，避免排版崩
        s.setMediaPlaybackRequiresUserGesture(true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                // 外鏈（更新下載）轉系統瀏覽器，不在應用內打開
                if (url.startsWith("http://") || url.startsWith("https://")) {
                    startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                    return true;
                }
                return false;
            }
        });

        webView.loadUrl("file:///android_asset/www/index.html");
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}