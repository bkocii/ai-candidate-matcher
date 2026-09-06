document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-password-target]").forEach((toggle) => {
        toggle.addEventListener("click", () => {
            const fields = document.querySelectorAll(toggle.dataset.passwordTarget);
            const shouldShow = [...fields].some((field) => field.type === "password");

            fields.forEach((field) => {
                field.type = shouldShow ? "text" : "password";
            });
            toggle.setAttribute("aria-pressed", String(shouldShow));
            toggle.textContent = shouldShow
                ? toggle.dataset.hideLabel
                : toggle.dataset.showLabel;
        });
    });
});
