document.addEventListener('DOMContentLoaded', function () {
    var homepage = document.querySelector('.badberg-homepage');
    if (!homepage) {
        return;
    }

    var navToggle = document.querySelector('[data-domain-nav-toggle]');
    var navPanel = document.querySelector('[data-domain-nav-panel]');
    if (navToggle && navPanel) {
        navToggle.addEventListener('click', function () {
            var isOpen = navPanel.classList.toggle('is-open');
            navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        });
    }

    var form = document.querySelector('[data-domain-mockup-form]');
    var input = document.getElementById('badberg-domain-input');
    var results = document.querySelector('[data-domain-mockup-results]');
    var variants = [
        {tld: 'de', available: true, price: '12,00 € / Jahr', detail: 'Domainregistrierung mit DNS-Unterstützung'},
        {tld: 'com', available: false, price: null, detail: 'Nicht mehr frei. Prüfe alternative Schreibweisen oder andere TLDs.'},
        {tld: 'eu', available: true, price: '9,00 € / Jahr', detail: 'Gute Ergänzung für europaweite Präsenz'},
        {tld: 'net', available: true, price: '13,00 € / Jahr', detail: 'Besonders passend für technische Angebote'},
        {tld: 'online', available: false, price: null, detail: 'Als Variante aktuell vergeben. Andere Endungen sind noch möglich.'},
    ];

    function normalizeBase(value) {
        var normalized = (value || '').trim().toLowerCase();
        normalized = normalized.replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
        normalized = normalized.replace(/[^a-z0-9.-]/g, '');
        if (!normalized) {
            return 'ihre-wunschdomain';
        }
        var parts = normalized.split('.').filter(Boolean);
        return parts.length > 1 ? parts[0] : normalized;
    }

    function renderResults(base) {
        if (!results) {
            return;
        }
        results.replaceChildren();
        variants.forEach(function (variant) {
            var domain = base + '.' + variant.tld;
            var article = document.createElement('article');
            article.className = 'badberg-result-card ' + (variant.available ? 'is-available' : 'is-unavailable');

            var content = document.createElement('div');
            var label = document.createElement('p');
            label.className = 'badberg-result-label';
            label.textContent = variant.available ? 'Verfügbar' : 'Bereits vergeben';

            var title = document.createElement('h3');
            title.textContent = domain;

            var detail = document.createElement('p');
            detail.textContent = variant.available ? variant.price + ' · ' + variant.detail : variant.detail;

            content.appendChild(label);
            content.appendChild(title);
            content.appendChild(detail);
            article.appendChild(content);

            if (variant.available) {
                var registerLink = document.createElement('a');
                registerLink.href = '/web/login?redirect=/my/domains/check';
                registerLink.className = 'badberg-result-action';
                registerLink.textContent = 'Registrieren';
                article.appendChild(registerLink);
            } else {
                var suggestionButton = document.createElement('button');
                suggestionButton.type = 'button';
                suggestionButton.className = 'badberg-result-action badberg-result-action-secondary';
                suggestionButton.setAttribute('data-domain-suggestion', base);
                suggestionButton.textContent = 'Alternative suchen';
                article.appendChild(suggestionButton);
            }

            results.appendChild(article);
        });

        bindSuggestionButtons();
    }

    function bindSuggestionButtons() {
        document.querySelectorAll('[data-domain-suggestion]').forEach(function (button) {
            button.addEventListener('click', function () {
                var suggestion = button.getAttribute('data-domain-suggestion') || 'ihre-wunschdomain';
                if (input) {
                    input.value = suggestion;
                    input.focus();
                }
                renderResults(suggestion);
            });
        });
    }

    if (form && input && results) {
        form.addEventListener('submit', function (event) {
            event.preventDefault();
            renderResults(normalizeBase(input.value));
            results.scrollIntoView({behavior: 'smooth', block: 'start'});
        });
    }

    bindSuggestionButtons();
});
