/* Bridge TMB pages that end on "Test complete!" without calling tmbSubmitToServer. */
(function () {
  function wrapShowAlert() {
    if (typeof showAlert !== "function" || showAlert.__trialspineBridge) {
      return;
    }
    var original = showAlert;
    function bridged(msg, btnText, onClick, fontSize, autoMs) {
      var text = typeof msg === "string" ? msg : "";
      var deadEnd =
        /test\s*complete/i.test(text) &&
        (!btnText || btnText === "") &&
        typeof tmbSubmitToServer === "function" &&
        Array.isArray(window.results);

      if (deadEnd) {
        tmbSubmitToServer(
          window.results,
          window.score != null ? window.score : "",
          window.outcomes || {}
        );
        return;
      }
      return original.apply(this, arguments);
    }
    bridged.__trialspineBridge = true;
    showAlert = bridged;
  }

  wrapShowAlert();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wrapShowAlert);
  }
  setTimeout(wrapShowAlert, 0);
  setTimeout(wrapShowAlert, 250);
})();
