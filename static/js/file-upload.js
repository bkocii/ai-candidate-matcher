document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-file-upload]").forEach((upload) => {
        const input = upload.querySelector('input[type="file"]');
        const list = upload.querySelector("[data-selected-files]");
        const form = upload.closest("form");
        const submit = form?.querySelector("[data-file-submit]");

        const render = () => {
            list.replaceChildren();
            [...input.files].forEach((file, index) => {
                const item = document.createElement("li");
                const name = document.createElement("span");
                const remove = document.createElement("button");
                name.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
                remove.type = "button";
                remove.textContent = "Remove";
                remove.addEventListener("click", () => {
                    const transfer = new DataTransfer();
                    [...input.files].forEach((candidate, candidateIndex) => {
                        if (candidateIndex !== index) transfer.items.add(candidate);
                    });
                    input.files = transfer.files;
                    render();
                });
                item.append(name, remove);
                list.append(item);
            });
            if (submit) submit.disabled = input.files.length === 0;
        };

        input.addEventListener("change", render);
        render();
    });
});
