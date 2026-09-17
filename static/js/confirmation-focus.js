document.addEventListener("DOMContentLoaded", () => {
    const confirmation = document.querySelector("[data-confirmation-focus]");
    if (!confirmation) {
        return;
    }

    confirmation.focus({ preventScroll: true });
    confirmation.scrollIntoView({ block: "start" });
});
