document.addEventListener("DOMContentLoaded", () => {
    const progress = document.querySelector("[data-profile-processing]");
    if (!progress || Number(progress.dataset.profileProcessing) < 1) return;

    const refreshWhenIdle = () => {
        const previewIsOpen = Boolean(progress.querySelector("details[open]"));
        if (document.visibilityState === "visible" && !previewIsOpen) {
            window.location.reload();
            return;
        }
        window.setTimeout(refreshWhenIdle, 4000);
    };
    window.setTimeout(refreshWhenIdle, 4000);
});
