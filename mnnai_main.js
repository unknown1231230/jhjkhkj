const { createApp } = Vue;

createApp({
    data() {
        return {
            isModalActive: false,
            menuOpen: false,
            isEnterprise: false,

            itemsPerSlide: 3,
            transitioning: true,
            offsetX: 0,
            carouselInterval: null,

            reviews: [
                {
                    id: 1,
                    name: 'Dayroet',
                    avatar: '/files/image_dayroet.png',
                    text: 'The beauty of AI technologies, the best website to try almost all new AI models for free',
                    link: 'https://discord.com/channels/1183405578823929856/1354807682808287232/1447165859872116876'
                },
                {
                    id: 2,
                    name: 'MM',
                    avatar: '/files/image_mm.png',
                    text: 'Honestly, MNN AI is the best provider I have found so far. He is sooo kind and helps a lot for free. All of this is thanks to the Russian man @Mkshustov 💋💖',
                    link: 'https://discord.com/channels/1183405578823929856/1354807682808287232/1413484110722371695'
                },
                {
                    id: 3,
                    name: '[ʀᴇᴅᴀᴄᴛᴇᴅ]',
                    avatar: '/files/image_redacted.png',
                    text: 'MNN AI has been one of my favourite APIs that actually care about users. The owner has been such an amazing guy. Hope that he maintains this as long as possible. ❤️',
                    link: 'https://discord.com/channels/1183405578823929856/1354807682808287232/1412131571468603472'
                },
                {
                    id: 4,
                    name: 'JayA',
                    avatar: '/files/image_jaya.png',
                    text: "I've tested all the models and I have to say that they are perfect, fast, and work very well. The API developer is extremely careful, generous and friendly. 🙏 🫶",
                    link: 'https://discord.com/channels/1183405578823929856/1354807682808287232/1395391337326579733'
                },
                {
                    id: 5,
                    name: 'Vadim11111',
                    avatar: '/files/image_vadim11111.png',
                    text: 'Best site ever, thanks to pixel number 456 894',
                    link: 'https://discord.com/channels/1183405578823929856/1354807682808287232/1440751381190541476'
                }
            ]
        };
    },
    computed: {
        trackStyle() {
            return {
                transform: `translateX(${this.offsetX}%)`,
                transition: this.transitioning ? 'transform 0.8s cubic-bezier(0.25, 1, 0.5, 1)' : 'none'
            };
        }
    },
    mounted() {
        this.setupModalListeners();

        this.checkScreenSize();
        this.startCarousel();

        window.addEventListener("resize", () => {
            this.checkScreenSize();

            if (window.innerWidth > 768 && this.menuOpen) {
                this.menuOpen = false;
                this.updateHamburgerClass();
                this.toggleGetStartedButton(false);
            }
        });

        setTimeout(this.handleScrollAnimations, 100);
        window.addEventListener('scroll', this.handleScrollAnimations, { passive: true });
    },
    beforeUnmount() {
        if (this.carouselInterval) clearInterval(this.carouselInterval);
    },
    methods: {
        checkScreenSize() {
            this.itemsPerSlide = window.innerWidth < 768 ? 1 : 3;
        },

        startCarousel() {
            this.carouselInterval = setInterval(() => {
                this.nextSlide();
            }, 3500);
        },

        nextSlide() {
            this.transitioning = true;

            const step = 100 / this.itemsPerSlide;
            this.offsetX = -step;

            setTimeout(() => {
                this.transitioning = false;

                const firstItem = this.reviews.shift();
                this.reviews.push(firstItem);

                this.offsetX = 0;

            }, 800);
        },

        toggleMenu() {
            this.menuOpen = !this.menuOpen;
            this.updateHamburgerClass();
            this.toggleGetStartedButton(this.menuOpen);
        },
        closeMenu() {
            this.menuOpen = false;
            this.updateHamburgerClass();
            this.toggleGetStartedButton(false);
        },
        updateHamburgerClass() {
            const hamburger = document.querySelector(".hamburger-menu");
            if (this.menuOpen) {
                hamburger.classList.add("active");
            } else {
                hamburger.classList.remove("active");
            }
        },

        toggleGetStartedButton(hide) {
            const getStartedBtn = document.querySelector('.mnn-portal');
            if (getStartedBtn) {
                if (hide) {
                    getStartedBtn.style.opacity = '0';
                    getStartedBtn.style.visibility = 'hidden';
                    getStartedBtn.style.pointerEvents = 'none';
                } else {
                    getStartedBtn.style.opacity = '1';
                    getStartedBtn.style.visibility = 'visible';
                    getStartedBtn.style.pointerEvents = 'auto';
                }
            }
        },
        setupModalListeners() {
            const handleModalOpen = async () => {
                const [cookiesData] = await Promise.all([this.getCookies()]);
                const { token } = cookiesData;
                if (token) {
                    window.location.href = '/chat';
                    return;
                }
                this.isModalActive = true;
                this.navbar(true);
            };

            const handleModalClose = () => {
                window.location.href = '/';
                this.isModalActive = false;
                this.navbar(false);
            };

            if (window.location.search.includes('login')) {
                handleModalOpen();
            } else {
                const startButtons = document.querySelectorAll('.mnn-portal');
                startButtons.forEach(btn => {
                    btn.addEventListener('click', handleModalOpen);
                });
            }

            document.querySelector('.close-modal').addEventListener('click', handleModalClose);
        },

        togglePricing() {
            this.isEnterprise = !this.isEnterprise;
        },

        navbar(isOpening) {
            const fptf = document.querySelector('.FPTF');
            const aife = document.querySelector('.AIFE');
            const modal = document.getElementById('authModal');
            const mnn = document.querySelector('.mnn');
            const navbar = document.querySelector('.navbar');
            const scroll = document.querySelector('.scroll-button');
            const body = document.body;

            if (isOpening) {
                modal.classList.remove('hidden');
                modal.classList.add('active');
                body.classList.add('no-scroll');
                if(fptf) fptf.style.zIndex = '-1';
                if(aife) aife.style.zIndex = '-1';
                if(scroll) scroll.style.zIndex = '-1';
                if (window.innerWidth < 768) {
                    if(mnn) mnn.style.zIndex = '-1';
                    if(navbar) navbar.style.zIndex = '-1';
                }
            } else {
                modal.classList.remove('active');
                modal.classList.add('hidden');
                body.classList.remove('no-scroll');
                if(fptf) fptf.style.zIndex = '1';
                if(aife) aife.style.zIndex = '1';
                if(scroll) scroll.style.zIndex = '1';
                if (window.innerWidth < 768) {
                    if(mnn) mnn.style.zIndex = '1';
                    if(navbar) navbar.style.zIndex = '1';
                }
            }
        },

        getCookies() {
            return fetch('/getcookies').then(response => response.json());
        },

        geturl() {
            return fetch('/geturl').then(response => response.json());
        },

        async redirectTo(provider) {
            try {
                const [urlData] = await Promise.all([this.geturl()]);
                const base_url = urlData.url;
                let url = '';

                const params = new URLSearchParams(window.location.search);
                const ref = params.get('ref');
                const querySuffix = ref ? `?ref=${ref}` : '';

                switch (provider) {
                    case 'google':
                        url = `/auth/google${querySuffix}`;
                        break;
                    case 'discord':
                        const discordCallback = `${base_url}/auth/discord${querySuffix}`;
                        url = `https://discord.com/oauth2/authorize?client_id=1216312009952464966&response_type=code&redirect_uri=${discordCallback}&scope=identify+email`;
                        break;
                    case 'github':
                        url = `https://github.com/login/oauth/authorize?client_id=Ov23lis4R1OjmTrmLs6e&redirect_uri=${base_url}/auth/github&scope=user:email`;
                        break;
                }
                window.location.href = url;
            } catch (error) {
                console.error('Error during redirect:', error);
            }
        },

        isInViewport(element) {
            const rect = element.getBoundingClientRect();
            return rect.top <= (window.innerHeight || document.documentElement.clientHeight) * 0.8;
        },

        handleScrollAnimations() {
            const animatedElements = document.querySelectorAll('.text-animate');
            animatedElements.forEach(el => {
                if (this.isInViewport(el)) {
                    el.classList.add('visible');
                }
            });
        }
    }
}).mount('#app');
