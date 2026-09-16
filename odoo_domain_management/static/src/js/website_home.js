document.addEventListener('DOMContentLoaded', function () {
    var homepage = document.querySelector('.badberg-homepage');
    if (!homepage) {
        return;
    }

    document.body.classList.add('badberg-homepage-active');

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
        results.innerHTML = variants.map(function (variant) {
            var domain = base + '.' + variant.tld;
            if (variant.available) {
                return (
                    '<article class="badberg-result-card is-available">' +
                        '<div>' +
                            '<p class="badberg-result-label">Verfügbar</p>' +
                            '<h3>' + domain + '</h3>' +
                            '<p>' + variant.price + ' · ' + variant.detail + '</p>' +
                        '</div>' +
                        '<a href="/web/login?redirect=/my/domains/check" class="badberg-result-action">Registrieren</a>' +
                    '</article>'
                );
            }
            return (
                '<article class="badberg-result-card is-unavailable">' +
                    '<div>' +
                        '<p class="badberg-result-label">Bereits vergeben</p>' +
                        '<h3>' + domain + '</h3>' +
                        '<p>' + variant.detail + '</p>' +
                    '</div>' +
                    '<button type="button" class="badberg-result-action badberg-result-action-secondary" data-domain-suggestion="' + base + '">Alternative suchen</button>' +
                '</article>'
            );
        }).join('');

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
