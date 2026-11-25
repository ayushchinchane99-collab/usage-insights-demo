/**
 * Minimal usage tracker with semantic action descriptions.
 *
 * Instead of sending raw clicks ("button#btn-17 clicked"), the application
 * calls track("add_to_cart", {...}) with a semantic action name. The tracker
 * enriches it with a human-readable description, the product feature, and a
 * session id, then sends it to the collector with navigator.sendBeacon so the
 * event survives page unloads (when the browser allows it).
 */
(function () {
  var ENDPOINT = "/events";

  var ACTIONS = {
    view_product_list: ["User opened the product catalogue", "catalogue"],
    search_products: ["User searched the catalogue with a text query", "search"],
    apply_filter: ["User filtered the catalogue by category or price", "filter"],
    view_product: ["User opened a product detail page", "catalogue"],
    add_to_wishlist: ["User saved a product to the wishlist", "wishlist"],
    add_to_cart: ["User added a product to the shopping cart", "cart"],
    view_cart: ["User opened the shopping cart", "cart"],
    remove_from_cart: ["User removed a product from the shopping cart", "cart"],
    start_checkout: ["User started the checkout process", "checkout"],
    enter_shipping: ["User completed the shipping address form", "checkout"],
    back_to_cart: ["User went back from checkout to the cart", "cart"],
    enter_payment: ["User completed the payment details form", "checkout"],
    submit_order: ["User submitted the order; the task is completed", "checkout"]
    // apply_promo_code is intentionally NOT instrumented (see README: gap analysis)
  };

  function sessionId() {
    try {
      var id = sessionStorage.getItem("uid_session");
      if (!id) {
        id = "s_" + Math.random().toString(36).slice(2, 10);
        sessionStorage.setItem("uid_session", id);
      }
      return id;
    } catch (e) {
      return "s_anonymous";
    }
  }

  window.track = function (action, extra) {
    var meta = ACTIONS[action];
    if (!meta) {
      console.warn("track(): unknown action", action);
      return;
    }
    var event = {
      session_id: sessionId(),
      ts: Date.now() / 1000,
      task: "checkout",
      action: action,
      description: meta[0],
      feature: meta[1],
      detail: extra || {}
    };
    var body = JSON.stringify(event);
    // text/plain avoids a CORS preflight request.
    if (navigator.sendBeacon) {
      navigator.sendBeacon(ENDPOINT, new Blob([body], { type: "text/plain" }));
    } else {
      fetch(ENDPOINT, { method: "POST", body: body, keepalive: true });
    }
  };
})();
