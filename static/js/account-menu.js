document.addEventListener("DOMContentLoaded", () => {
    const menus = document.querySelectorAll(".account-menu");

    document.addEventListener("click", (event) => {
        menus.forEach((menu) => {
            if (menu.open && !menu.contains(event.target)) {
                menu.open = false;
            }
        });
    });

    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") return;
        menus.forEach((menu) => {
            if (!menu.open) return;
            menu.open = false;
            menu.querySelector("summary")?.focus();
        });
    });
});
