/** @odoo-module **/

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

class DomainSearch extends Interaction {
    static selector = ".js_domain_search_form";

    dynamicContent = {
        _root: {
            "t-on-submit": this.onSubmit,
        },
    };

    async onSubmit(ev) {
        ev.preventDefault();
        const container = this.el.parentElement.querySelector(".js_domain_search_results");
        if (!container) {
            return;
        }
        container.innerHTML =
            '<div class="text-center py-3"><i class="fa fa-spinner fa-spin"></i></div>';
        try {
            const formData = new FormData(this.el);
            const response = await fetch(this.el.dataset.action || "/domains/search", {
                method: "POST",
                body: formData,
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            if (response.ok) {
                container.innerHTML = await response.text();
            } else {
                container.innerHTML = "";
            }
        } catch (err) {
            container.innerHTML = "";
        }
    }
}

class DomainPricing extends Interaction {
    static selector = ".js_domain_pricing";

    start() {
        this.load();
    }

    async load() {
        try {
            const response = await fetch(this.el.dataset.action || "/domains/pricing", {
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            if (response.ok) {
                this.el.innerHTML = await response.text();
            }
        } catch (err) {
            // dynamic pricing is non-critical; ignore
        }
    }
}

registry.category("public.interactions").add(
    "odoo_domain_management.domain_search",
    DomainSearch
);
registry.category("public.interactions").add(
    "odoo_domain_management.domain_pricing",
    DomainPricing
);
