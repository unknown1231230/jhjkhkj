const { createApp } = Vue;

const clickOutside = {
    mounted(el, binding) {
        el._clickOutside = (event) => {
            if (!(el === event.target || el.contains(event.target))) {
                binding.value(event);
            }
        };
        document.addEventListener('click', el._clickOutside, true);
    },
    unmounted(el) {
        document.removeEventListener('click', el._clickOutside, true);
    }
};

createApp({
    directives: {
        clickOutside
    },
    data() {
        return {
            plans: {
                basic: 5,
                pro: 10,
                ultra: 15,
                enterprise: 30
            },
            currentPage: 'dashboard',
            sidebarCollapsed: false,
            userData: null,
            loading: true,
            error: null,
            showDropdown: false,
            showModal: false,

            newApiKeyName: '',
            newApiKey: '',
            generatedKeyName: '',
            showNewApiKey: false,
            showCreateKeyModal: false,
            keyToDelete: null,
            generatingKey: false,
            copied: false,
            keysError: null,
            loadingKeys: false,

            selectedModel: '',
            userPrompt: '',
            modelResponse: '',
            modelImageResponse: '',
            modelRunning: false,

            charts: {},
            chartsInitialized: false,
            chartInitRetries: 0,
            maxChartRetries: 10,
            isMobileView: window.innerWidth <= 992,
            sidebarVisible: window.innerWidth > 992,
            token: null,
            resizeTimeout: null,
            chartInitTimeout: null,

            apiUrl: '',
            availableModels: [],
            textModels: [],
            imageModels: [],
            loadingModels: false,

            walletDigits: '',
            submittingPayment: false,
            paymentSuccess: false,
            paymentError: null,
            copiedAddresses: {
                usdt: false,
                btc: false,
                ton: false,
                eth: false
            },
            selectedPlan: { price: 5.00 },

            selectedPaymentMethod: null,
            showPromoModal: false,
            promoCode: '',
            promoSubmitting: false,
            promoSuccess: false,
            promoBonus: '',
            promoError: null,

            tierData: {
                'free': {
                    name: 'Free',
                    rpm: 5,
                    models: 'Only Free models',
                    features: { webSearch: true, functionCalling: false, audio: false }
                },
                'basic': {
                    name: 'Basic',
                    rpm: 10,
                    models: 'Free & Basic models',
                    features: { webSearch: true, functionCalling: true, audio: true }
                },
                'pro': {
                    name: 'Pro',
                    rpm: 20,
                    models: 'All models',
                    features: { webSearch: true, functionCalling: true, audio: true }
                },
                'ultra': {
                    name: 'Ultra',
                    rpm: 40,
                    models: 'All models',
                    features: { webSearch: true, functionCalling: true, audio: true }
                },
                'enterprise': {
                    name: 'Enterprise',
                    rpm: 100,
                    models: 'All models',
                    features: { webSearch: true, functionCalling: true, audio: true }
                },
                'ultra_old': {
                    name: 'Ultra (Old)',
                    rpm: 40,
                    models: 'All models',
                    features: { webSearch: true, functionCalling: true, audio: true }
                }
            },
        };
    },
    computed: {
        isImageModel() {
            const model = this.availableModels.find(m => m.id === this.selectedModel);
            return model && model.type === 'images.generations';
        },
        formattedResponse() {
            if (!this.modelResponse) return '';
            let formatted = this.modelResponse
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.+?)\*/g, '<em>$1</em>')
                .replace(/```([\s\S]*?)```/g, (match, p1) => `<pre><code>${p1.trim()}</code></pre>`)
                .replace(/`(.+?)`/g, '<code>$1</code>')
                .replace(/\n/g, '<br>');
            return formatted;
        },
        currentTierData() {
            if (this.userData && this.userData.tariff) {
                const tierKey = this.userData.tariff.toLowerCase();
                return this.tierData[tierKey] || this.tierData['free'];
            }
            return this.tierData['free'];
        }
    },
    watch: {
        userData(newUserData) {
            if (newUserData && newUserData.total_requests !== undefined) {
                if (this.currentPage === 'dashboard' && !this.chartsInitialized) {
                    this.scheduleChartInit();
                }
            }
        },
        currentPage(newPage, oldPage) {
            if (oldPage === 'dashboard' && newPage !== 'dashboard') {
                this.clearChartTimeout();
                this.destroyAllCharts();
            }

            if (newPage === 'dashboard' && this.userData && this.userData.total_requests !== undefined && !this.loading) {
                this.scheduleChartInit();
            }
            if (newPage === 'workbench' && this.availableModels.length === 0) {
                this.fetchModels();
            }
            if (newPage !== 'apikeys') {
                this.keysError = null;
            }
            if (newPage === 'apikeys' && this.userData && !this.userData.keys_fetched) {
                this.fetchUserKeys();
            }
            if (newPage === 'billing') {
                this.selectedPaymentMethod = null;
            }
        }
    },
    methods: {
        selectPaymentMethod(method) {
            this.selectedPaymentMethod = method;
        },

        goBackToPaymentMethods() {
            this.selectedPaymentMethod = null;
        },

        openPromoModal() {
            this.showPromoModal = true;
            this.closeDropdown();
            this.promoCode = '';
            this.promoSuccess = false;
            this.promoBonus = '';
            this.promoError = null;
        },

        closePromoModal() {
            this.showPromoModal = false;
            this.promoCode = '';
            this.promoSuccess = false;
            this.promoBonus = '';
            this.promoError = null;
        },

        async submitPromoCode() {
            if (!this.promoCode.trim() || this.promoSubmitting) return;

            try {
                this.promoSubmitting = true;
                this.promoError = null;
                this.promoSuccess = false;
                this.promoBonus = '';

                const recaptchaToken = await this.loadRecaptcha();
                const response = await axios.post('/promo', {
                    promo_code: this.promoCode.trim(),
                    recaptcha_token: recaptchaToken
                }, {
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': this.token
                    }
                });

                if (response.data.status === true) {
                    this.promoSuccess = true;
                    this.promoBonus = response.data.bonus || 'Promo code applied!';
                    this.promoCode = '';
                    await this.fetchUserData();
                } else {
                    this.promoError = response.data.error || 'Invalid promo code';
                }

            } catch (err) {
                this.promoError = err.response?.data?.error || err.message || 'Failed to apply promo code. Please try again.';
                console.error('Promo code error:', err);
            } finally {
                this.promoSubmitting = false;
            }
        },

        selectPlan(name, price) {
            this.selectedPlan = { name: name.charAt(0).toUpperCase() + name.slice(1), price };

            this.$nextTick(() => {
                setTimeout(() => {
                    const paymentDetails = document.querySelector('.payment-verification');
                    if (paymentDetails) {
                        paymentDetails.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start',
                            inline: 'nearest'
                        });
                    }
                }, 100);
            });
        },

        copyAddress(address, crypto) {
            navigator.clipboard.writeText(address)
                .then(() => {
                    this.copiedAddresses[crypto] = true;
                    setTimeout(() => {
                        this.copiedAddresses[crypto] = false;
                    }, 2000);
                })
                .catch(err => {
                    console.error('Failed to copy address:', err);
                    this.paymentError = 'Failed to copy address to clipboard';
                });
        },

        async submitPaymentRequest() {
            if (this.walletDigits.length !== 4 || this.submittingPayment) return;
            try {
                this.submittingPayment = true;
                this.paymentError = null;
                this.paymentSuccess = false;

                const recaptchaToken = await this.loadRecaptcha();
                const response = await axios.post('/payment', {
                    last_digits: this.walletDigits,
                    recaptcha_token: recaptchaToken
                }, {
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': this.token
                    }
                });

                this.paymentSuccess = true;
                setTimeout(() => {
                    this.paymentError = null;
                }, 5000);

            } catch (err) {
                this.paymentError = err.response?.data?.error || err.message || 'Failed to submit payment request. Please try again.';
                console.error('Payment submission error:', err);
                setTimeout(() => {
                    this.paymentError = null;
                }, 5000);
            } finally {
                this.submittingPayment = false;
            }
        },

        async checkToken() {
            const cookiesData = await this.getCookies();
            if (!this.token) {
                window.location.href = '/?login&ref=dashboard';
            }
        },

        async getCookies() {
            try {
                const response = await fetch('/getcookies', { method: 'GET' });
                if (response.ok) {
                    const data = await response.json();
                    this.token = data.token;
                    return data;
                } else {
                    this.token = null;
                    return {};
                }
            } catch (error) {
                console.error('Error fetching cookies:', error);
                this.token = null;
                return {};
            }
        },

        async fetchApiUrl() {
            try {
                const response = await fetch('/geturl', {
                    method: 'GET',
                    headers: { 'Authorization': this.token }
                });
                if (response.ok) {
                    const data = await response.json();
                    this.apiUrl = data.apiurl;
                    return data.apiurl;
                } else {
                    throw new Error('Failed to fetch API URL');
                }
            } catch (error) {
                console.error('Error fetching API URL:', error);
                this.error = 'Failed to fetch API configuration';
                return null;
            }
        },

        async fetchModels() {
            if (!this.apiUrl) {
                await this.fetchApiUrl();
            }
            if (!this.apiUrl) return;

            try {
                this.loadingModels = true;
                const response = await fetch(`${this.apiUrl}/v1/models`, {
                    method: 'GET',
                    headers: { 'Authorization': this.token }
                });

                if (response.ok) {
                    const data = await response.json();
                    this.availableModels = data.data || [];

                    this.textModels = this.availableModels.filter(m => m.type === 'chat.completions');
                    this.imageModels = this.availableModels.filter(m => m.type === 'images.generations');

                    if (!this.selectedModel && this.textModels.length > 0) {
                        const defaultModel = this.textModels.find(m => m.id === 'gpt-4.1-mini') || this.textModels[0];
                        this.selectedModel = defaultModel.id;
                    }
                } else {
                    throw new Error('Failed to fetch models');
                }
            } catch (error) {
                console.error('Error fetching models:', error);
                this.error = 'Failed to load available models';
            } finally {
                this.loadingModels = false;
            }
        },

        navigateTo(page) {
            if (page === 'docs') {
                window.location.href = '/docs';
                return;
            }
            if (page === 'feedback') {
                window.open('https://discord.com/invite/tXmSgWXF2N', '_blank');
                return;
            }

            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.has('billing') && page !== 'billing') {
                window.history.pushState({}, '', '/dashboard');
            }

            if (page === 'billing') {
                this.currentPage = 'billing';
                window.history.pushState({}, '', '/dashboard?billing');
                if (this.isMobileView && this.sidebarVisible) {
                    this.sidebarVisible = false;
                }
                return;
            }

            this.clearChartTimeout();
            this.currentPage = page;

            if (this.isMobileView && this.sidebarVisible) {
                this.sidebarVisible = false;
            }
        },

        async runModel() {
            if (this.userPrompt.trim() === '' || this.modelRunning) return;

            if (!this.apiUrl) {
                await this.fetchApiUrl();
                if (!this.apiUrl) {
                    this.modelResponse = 'Error: Failed to get API configuration';
                    return;
                }
            }

            try {
                this.modelRunning = true;
                this.modelResponse = '';
                this.modelImageResponse = '';
                const headers = {
                    'Authorization': this.token,
                    'Content-Type': 'application/json'
                };

                if (this.isImageModel) {
                    const endpoint = `${this.apiUrl}/v1/images/generations`;
                    const response = await axios.post(endpoint, {
                        model: this.selectedModel,
                        prompt: this.userPrompt,
                        negative_prompt: "",
                        response_format: "b64_json"
                    }, { headers });
                    this.modelImageResponse = 'data:image/png;base64,' + response.data?.data?.[0]?.b64_json;
                } else {
                    const endpoint = `${this.apiUrl}/v1/chat/completions`;
                    if ('TextDecoder' in window && 'ReadableStream' in window) {
                        headers['Accept'] = 'text/event-stream';
                        const body = {
                            model: this.selectedModel,
                            messages: [{ role: 'user', content: this.userPrompt }],
                            temperature: 0.5,
                            stream: true
                        };
                        const response = await fetch(endpoint, {
                            method: 'POST',
                            headers: headers,
                            body: JSON.stringify(body)
                        });
                        if (!response.ok) {
                            const errorData = await response.json().catch(() => ({ detail: response.statusText }));
                            throw new Error(`HTTP error! status: ${response.status} - ${errorData.detail || errorData.error || ''}`);
                        }
                        const reader = response.body.getReader();
                        const decoder = new TextDecoder();
                        let buffer = '';
                        this.modelResponse = '';
                        while (true) {
                            const { done, value } = await reader.read();
                            if (done) break;
                            buffer += decoder.decode(value, { stream: true });
                            let newlineIndex;
                            while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
                                const line = buffer.slice(0, newlineIndex);
                                buffer = buffer.slice(newlineIndex + 1);
                                if (line.startsWith('data: ')) {
                                    const data = line.slice(6);
                                    if (data === '[DONE]') continue;
                                    try {
                                        const parsed = JSON.parse(data);
                                        const content = parsed.choices[0]?.delta?.content || '';
                                        if (content) {
                                            this.modelResponse += content;
                                        }
                                    } catch (e) {
                                        console.error('Error parsing streaming data:', e, "Data:", data);
                                    }
                                }
                            }
                        }
                        if (buffer.startsWith('data: ')) {
                            const data = buffer.slice(6);
                            if (data !== '[DONE]') {
                                try {
                                    const parsed = JSON.parse(data);
                                    const content = parsed.choices[0]?.delta?.content || '';
                                    if (content) {
                                        this.modelResponse += content;
                                    }
                                } catch (e) {
                                    console.error('Error parsing final buffer:', e, "Buffer:", data);
                                }
                            }
                        }
                    } else {
                        const response = await axios.post(endpoint, {
                            model: this.selectedModel,
                            messages: [{ role: 'user', content: this.userPrompt }],
                            temperature: 0.5,
                            stream: false
                        }, { headers });
                        if (response.data?.choices?.[0]?.message?.content) {
                            this.modelResponse = response.data.choices[0].message.content;
                        }
                    }
                }
            } catch (err) {
                console.error('Model run error:', err);
                this.modelResponse = 'Error: Failed to run the model. ' +
                    (err.response?.data?.Error || err.response?.data?.detail || err.message || 'Please try again.');
            } finally {
                this.modelRunning = false;
            }
        },

        setCurrentPageFromPath(path) {
            const validPages = ['dashboard', 'workbench', 'apikeys', 'billing', 'limits'];
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.has('billing')) {
                this.currentPage = 'billing';
                return;
            }
            const pageName = path.split('?')[0];
            if (validPages.includes(pageName)) {
                this.currentPage = pageName;
            } else {
                this.currentPage = 'dashboard';
            }
        },

        toggleSidebar() {
            if (this.isMobileView) {
                this.sidebarVisible = !this.sidebarVisible;
            } else {
                this.sidebarCollapsed = !this.sidebarCollapsed;
                if (this.currentPage === 'dashboard' && this.userData) {
                    this.clearChartTimeout();
                    this.chartInitTimeout = setTimeout(() => {
                        if (this.currentPage === 'dashboard') {
                            this.chartInitRetries = 0;
                            this.chartsInitialized = false;
                            this.destroyAllCharts();
                            this.scheduleChartInit();
                        }
                    }, 300);
                }
            }
        },

        toggleDropdown() { this.showDropdown = !this.showDropdown; },
        closeDropdown() { this.showDropdown = false; },
        showAboutModal() { this.showModal = true; this.closeDropdown(); },
        closeModal() { this.showModal = false; },

        handleKeyDown(event) {
            if (event.key === 'Escape') {
                if (this.showModal) this.closeModal();
                if (this.showDropdown) this.closeDropdown();
                if (this.showNewApiKey) this.hideNewApiKey();
                if (this.showCreateKeyModal) this.closeCreateKeyModal();
                if (this.keyToDelete) this.cancelDeleteKey();
                if (this.showPromoModal) this.closePromoModal();
            }
        },

        getUserInitials() {
            if (!this.userData || !this.userData.username) return 'M';
            const nameParts = this.userData.username.split(' ');
            if (nameParts.length >= 2) {
                return (nameParts[0][0] + nameParts[1][0]).toUpperCase();
            } else if (nameParts.length === 1 && nameParts[0].length > 0) {
                return nameParts[0].substring(0, 2).toUpperCase();
            }
            return 'M';
        },

        async loadRecaptcha() {
            const RECAPTCHA_SITE_KEY = '6LfOS_QpAAAAAFyDDqNzLNQMJvdl0Pke3G3ekYoz';
            return new Promise((resolve, reject) => {
                if (typeof grecaptcha !== 'undefined' && grecaptcha.execute) {
                    grecaptcha.execute(RECAPTCHA_SITE_KEY, { action: 'submit' }).then(resolve).catch(reject);
                } else {
                    if (!document.querySelector('script[src*="recaptcha/api.js"]')) {
                        const script = document.createElement('script');
                        script.src = `https://www.google.com/recaptcha/api.js?render=${RECAPTCHA_SITE_KEY}`;
                        script.async = true;
                        script.defer = true;
                        document.head.appendChild(script);
                        script.onload = () => {
                            grecaptcha.ready(() => {
                                grecaptcha.execute(RECAPTCHA_SITE_KEY, { action: 'submit' }).then(resolve).catch(reject);
                            });
                        };
                        script.onerror = () => reject(new Error('reCAPTCHA script failed to load.'));
                    } else {
                        grecaptcha.ready(() => {
                            grecaptcha.execute(RECAPTCHA_SITE_KEY, { action: 'submit' }).then(resolve).catch(reject);
                        });
                    }
                }
            });
        },

        async fetchUserData() {
            try {
                this.loading = true;
                this.error = null;
                const recaptchaToken = await this.loadRecaptcha();
                const response = await axios.post('/getdata', {
                    Recaptcha: recaptchaToken
                }, {
                    headers: { 'Content-Type': 'application/json', 'Authorization': this.token }
                });
                this.userData = response.data;
                this.userData.keys_fetched = !!this.userData.keys;

            } catch (err) {
                this.error = 'Failed to fetch user data. Please refresh.';
                console.error('Error fetching user data:', err.response?.data || err.message || err);
                if (err.response?.status === 403 || err.response?.status === 401) {
                    window.location.href = '/?login&ref=dashboard';
                }
            } finally {
                this.loading = false;
            }
        },

        async fetchUserKeys() {
            if (!this.userData) return;
            this.loadingKeys = true;
            this.keysError = null;
            try {
                const recaptchaToken = await this.loadRecaptcha();
                const response = await axios.post('/getdata', {
                    Recaptcha: recaptchaToken
                }, {
                    headers: { 'Content-Type': 'application/json', 'Authorization': this.token }
                });
                this.userData.keys = response.data.keys;
                this.userData.keys_fetched = true;
            } catch (err) {
                this.keysError = 'Failed to refresh API keys.';
                console.error('Error fetching user keys:', err.response?.data || err.message || err);
            } finally {
                this.loadingKeys = false;
            }
        },

        async logout() {
            try {
                this.loading = true;
                this.destroyAllCharts();
                await axios.get('/logout');
                this.token = null;
                this.userData = null;
                window.location.href = '/?login&ref=dashboard';
            } catch (err) {
                this.error = 'Failed to logout. Please try again.';
                console.error('Logout error:', err);
                this.loading = false;
            }
        },

        clearChartTimeout() {
            if (this.chartInitTimeout) {
                clearTimeout(this.chartInitTimeout);
                this.chartInitTimeout = null;
            }
        },

        destroyAllCharts() {
            this.clearChartTimeout();

            const chartIds = ['apiUsageChart', 'modelDistributionChart', 'requestsChart'];

            chartIds.forEach(chartId => {
                try {
                    const canvas = document.getElementById(chartId);
                    if (canvas && typeof Chart !== 'undefined') {
                        const existingChart = Chart.getChart(canvas);
                        if (existingChart) {
                            existingChart.destroy();
                        }
                    }
                } catch (e) {}
            });

            Object.keys(this.charts).forEach(chartId => {
                if (this.charts[chartId]) {
                    try {
                        this.charts[chartId].destroy();
                    } catch (e) {}
                }
            });

            this.charts = {};
            this.chartsInitialized = false;
        },

        scheduleChartInit() {
            if (this.currentPage !== 'dashboard') {
                return;
            }

            this.clearChartTimeout();
            this.chartInitRetries = 0;
            this.chartsInitialized = false;

            this.destroyAllCharts();

            this.$nextTick(() => {
                this.chartInitTimeout = setTimeout(() => {
                    this.tryInitCharts();
                }, 50);
            });
        },

        tryInitCharts() {
            if (this.currentPage !== 'dashboard') {
                return;
            }

            if (!this.userData || this.userData.total_requests === undefined || typeof Chart === 'undefined') {
                return;
            }

            if (this.chartsInitialized) {
                return;
            }

            const apiUsageCanvas = document.getElementById('apiUsageChart');
            const modelDistributionCanvas = document.getElementById('modelDistributionChart');
            const requestsCanvas = document.getElementById('requestsChart');

            if (!apiUsageCanvas || !modelDistributionCanvas || !requestsCanvas) {
                this.chartInitRetries++;
                if (this.chartInitRetries < this.maxChartRetries) {
                    this.chartInitTimeout = setTimeout(() => {
                        this.tryInitCharts();
                    }, 100);
                }
                return;
            }

            this.initDashboardCharts();
        },

        initDashboardCharts() {
            if (this.currentPage !== 'dashboard') {
                return;
            }

            if (!this.userData || this.userData.total_requests === undefined || typeof Chart === 'undefined') {
                return;
            }

            if (this.chartsInitialized) {
                return;
            }

            const chartIds = ['apiUsageChart', 'modelDistributionChart', 'requestsChart'];
            const canvases = {};

            for (const id of chartIds) {
                const canvas = document.getElementById(id);
                if (!canvas) {
                    return;
                }

                try {
                    const existingChart = Chart.getChart(canvas);
                    if (existingChart) {
                        existingChart.destroy();
                    }
                } catch (e) {}

                canvases[id] = canvas;
            }

            this.charts = {};

            const commonOptions = {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: 'rgba(224, 224, 224, 0.8)',
                            font: { family: 'Manrope', size: 11 },
                            padding: 10,
                            boxWidth: 12,
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(30, 30, 30, 0.9)',
                        titleColor: '#ffffff',
                        bodyColor: '#e0e0e0',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        padding: 10,
                        cornerRadius: 6,
                        displayColors: true,
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.raw || 0;
                                return `${label}: ${value.toLocaleString()}`;
                            }
                        }
                    }
                },
                animation: {
                    animateRotate: true,
                    animateScale: true,
                    duration: 1200,
                    easing: 'easeOutQuart'
                }
            };

            const grayscalePalette = [
                'rgb(96, 102, 94)',
                'rgb(97, 113, 120)',
                'rgb(168, 181, 169)'
            ];

            const createChart = (canvas, canvasId, dataValues, colors) => {
                if (this.currentPage !== 'dashboard' || !canvas) {
                    return null;
                }

                const ctx = canvas.getContext('2d');
                if (!ctx) {
                    return null;
                }

                try {
                    return new Chart(canvas, {
                        type: 'doughnut',
                        data: {
                            labels: ['API Requests', 'Images', 'Tokens'],
                            datasets: [{
                                data: dataValues,
                                backgroundColor: colors,
                                borderColor: 'rgba(0, 0, 0, 0.1)',
                                borderWidth: 1,
                                hoverOffset: 10
                            }]
                        },
                        options: commonOptions
                    });
                } catch (error) {
                    console.error(`Failed to create chart ${canvasId}:`, error);
                    return null;
                }
            };

            if (this.userData.total_requests !== undefined && canvases['apiUsageChart']) {
                const chart = createChart(
                    canvases['apiUsageChart'],
                    'apiUsageChart',
                    [this.userData.total_requests || 0, this.userData.total_images || 0, this.userData.total_tokens || 0],
                    grayscalePalette
                );
                if (chart) this.charts['apiUsageChart'] = chart;
            }

            if (this.userData.total_requests_day !== undefined && canvases['modelDistributionChart']) {
                const chart = createChart(
                    canvases['modelDistributionChart'],
                    'modelDistributionChart',
                    [this.userData.total_requests_day || 0, this.userData.total_images_day || 0, this.userData.total_tokens_day || 0],
                    [grayscalePalette[1], grayscalePalette[2], grayscalePalette[0]]
                );
                if (chart) this.charts['modelDistributionChart'] = chart;
            }

            if (this.userData.total_requests_month !== undefined && canvases['requestsChart']) {
                const chart = createChart(
                    canvases['requestsChart'],
                    'requestsChart',
                    [this.userData.total_requests_month || 0, this.userData.total_images_month || 0, this.userData.total_tokens_month || 0],
                    [grayscalePalette[2], grayscalePalette[0], grayscalePalette[1]]
                );
                if (chart) this.charts['requestsChart'] = chart;
            }

            this.chartsInitialized = true;
        },

        closeCreateKeyModal() {
            this.showCreateKeyModal = false;
            this.newApiKeyName = '';
            this.keysError = null;
        },

        async generateApiKey() {
            if (!this.newApiKeyName.trim() || this.generatingKey) return;
            try {
                this.generatingKey = true;
                this.keysError = null;
                const recaptchaToken = await this.loadRecaptcha();
                const response = await axios.post('/genkey', {
                    Recaptcha: recaptchaToken,
                    name: this.newApiKeyName.trim()
                }, {
                    headers: { 'Content-Type': 'application/json', 'Authorization': this.token }
                });
                this.newApiKey = response.data.key;
                this.generatedKeyName = this.newApiKeyName.trim();

                this.showCreateKeyModal = false;
                this.showNewApiKey = true;

                this.newApiKeyName = '';
                await this.fetchUserKeys();
            } catch (err) {
                this.keysError = 'Failed to generate API key: ' + (err.response?.data?.error || err.message || "Please try again.");
                console.error('API key generation error:', err.response?.data || err.message || err);
            } finally {
                this.generatingKey = false;
            }
        },

        copyApiKey() {
            navigator.clipboard.writeText(this.newApiKey)
                .then(() => {
                    this.copied = true;
                    setTimeout(() => { this.copied = false; }, 2000);
                })
                .catch(err => { console.error('Failed to copy API key:', err); });
        },

        hideNewApiKey() {
            this.showNewApiKey = false;
            this.newApiKey = '';
            this.generatedKeyName = '';
            this.keysError = null;
        },

        confirmDeleteKey(keyName) {
            if (keyName === 'default') {
                this.keysError = "The 'default' key cannot be deleted.";
                setTimeout(() => this.keysError = null, 3000);
                return;
            }
            this.keyToDelete = keyName;
        },

        cancelDeleteKey() {
            this.keyToDelete = null;
        },

        async deleteApiKey() {
            if (!this.keyToDelete) return;

            try {
                this.loadingKeys = true;
                this.keysError = null;
                const recaptchaToken = await this.loadRecaptcha();
                await axios.post('/removekey', {
                    key_name: this.keyToDelete,
                    Recaptcha: recaptchaToken
                }, {
                    headers: { 'Content-Type': 'application/json', 'Authorization': this.token }
                });
                this.keyToDelete = null;
                await this.fetchUserKeys();
            } catch (err) {
                this.keysError = `Failed to delete API key: ${err.response?.data?.error || err.message || "Please try again."}`;
                console.error('API key deletion error:', err.response?.data || err.message || err);
                this.keyToDelete = null;
            } finally {
                this.loadingKeys = false;
            }
        },

        formatDate(timestamp) {
            if (!timestamp) return 'Unknown';
            const date = new Date(timestamp);
            if (isNaN(date.getTime())) return 'Invalid Date';
            return date.toLocaleDateString('en-US', {
                year: 'numeric', month: 'short', day: 'numeric',
            });
        },

        handleResize() {
            const currentlyMobile = window.innerWidth <= 992;
            if (this.isMobileView !== currentlyMobile) {
                this.isMobileView = currentlyMobile;
                if (this.isMobileView) {
                    this.sidebarCollapsed = false;
                    this.sidebarVisible = false;
                } else {
                    this.sidebarVisible = true;
                }
            }

            if (this.currentPage === 'dashboard' && this.userData) {
                clearTimeout(this.resizeTimeout);
                this.resizeTimeout = setTimeout(() => {
                    if (this.currentPage === 'dashboard') {
                        this.chartsInitialized = false;
                        this.scheduleChartInit();
                    }
                }, 250);
            }
        },

        handleGlobalClick(event) {
            if (this.isMobileView && this.sidebarVisible) {
                const sidebar = document.querySelector('.sidebar');
                const mobileToggle = document.querySelector('.mobile-nav-toggle');
                if (sidebar && !sidebar.contains(event.target) && mobileToggle && !mobileToggle.contains(event.target)) {
                    this.sidebarVisible = false;
                }
            }
        }
    },
    async mounted() {
        await this.checkToken();
        if (this.token) {
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.has('billing')) {
                this.currentPage = 'billing';
            } else {
                const path = window.location.pathname.substring(1);
                this.setCurrentPageFromPath(path || 'dashboard');
            }

            await this.fetchUserData();

            const planFromUrl = urlParams.get('plan');
            if (planFromUrl && this.plans[planFromUrl.toLowerCase()]) {
                const planName = planFromUrl.toLowerCase();
                const planPrice = this.plans[planName];
                this.selectPlan(planName, planPrice);
            } else {
                this.selectPlan('basic', this.plans.basic);
            }
        }

        document.addEventListener('keydown', this.handleKeyDown);
        window.addEventListener('resize', this.handleResize);
        document.addEventListener('click', this.handleGlobalClick, true);
    },
    beforeUnmount() {
        document.removeEventListener('keydown', this.handleKeyDown);
        window.removeEventListener('resize', this.handleResize);
        document.removeEventListener('click', this.handleGlobalClick, true);

        if (this.resizeTimeout) {
            clearTimeout(this.resizeTimeout);
        }
        this.clearChartTimeout();
        this.destroyAllCharts();
    }
}).mount('#app');