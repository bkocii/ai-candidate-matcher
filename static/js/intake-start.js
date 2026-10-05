document.addEventListener("DOMContentLoaded", () => {
    const context = document.querySelector("[data-intake-context]");
    if (!context) return;

    const vacancy = context.querySelector("select[name='vacancy']");
    const poolSettings = context.querySelector("[data-pool-settings]");
    const vacancySettings = context.querySelector("[data-vacancy-settings]");
    if (!vacancy || !poolSettings || !vacancySettings) return;

    const update = () => {
        const usesVacancy = Boolean(vacancy.value);
        poolSettings.hidden = usesVacancy;
        vacancySettings.hidden = !usesVacancy;
    };
    vacancy.addEventListener("change", update);
    update();
});
