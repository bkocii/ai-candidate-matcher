document.querySelectorAll("[data-eligibility-rule-form]").forEach((form) => {
    const criterion = form.querySelector("select[name$='rule_type']");
    const fields = {
        skill: form.querySelector("[data-rule-value='skill']"),
        numeric: form.querySelector("[data-rule-value='numeric']"),
        expected: form.querySelector("[data-rule-value='expected']"),
    };
    const render = () => {
        const visible = criterion.value === "required_skill"
            ? "skill"
            : criterion.value === "minimum_experience"
                ? "numeric"
                : "expected";
        Object.entries(fields).forEach(([name, field]) => {
            field.hidden = name !== visible;
            field.querySelectorAll("input, select, textarea").forEach((control) => {
                control.disabled = name !== visible;
            });
        });
    };
    criterion.addEventListener("change", render);
    render();
});

document.querySelectorAll("[data-eligibility-list]").forEach((group) => {
    const source = document.getElementById(group.dataset.sourceId);
    const target = group.querySelector(`[id="id_${group.dataset.fieldName}"]`);
    const emptyNote = group.querySelector(".eligibility-empty-note");
    if (!source || !target) {
        return;
    }

    const render = () => {
        const checked = new Set(
            Array.from(target.querySelectorAll("input:checked"), (input) => (
                input.value.trim().toLocaleLowerCase()
            )),
        );
        const seen = new Set();
        const values = source.value
            .split(/\r?\n/)
            .map((value) => value.trim())
            .filter((value) => {
                const key = value.toLocaleLowerCase();
                if (!value || seen.has(key)) {
                    return false;
                }
                seen.add(key);
                return true;
            });

        target.replaceChildren();
        values.forEach((value, index) => {
            const row = document.createElement("div");
            const label = document.createElement("label");
            const input = document.createElement("input");
            input.type = "checkbox";
            input.name = group.dataset.fieldName;
            input.value = value;
            input.id = `id_${group.dataset.fieldName}_${index}`;
            input.checked = checked.has(value.toLocaleLowerCase());
            label.htmlFor = input.id;
            label.append(input, document.createTextNode(value));
            row.append(label);
            target.append(row);
        });
        emptyNote.hidden = values.length > 0;
    };

    source.addEventListener("input", render);
    render();
});
