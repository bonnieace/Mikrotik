<script setup lang="ts">
import TitleComponent from '@/components/TitleComponent.vue';

</script>

<style>
[v-cloak] {
  display: none;
}
.gradient-bg {
  background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
}
.code-block {
  background-color: #1e293b;
  border-radius: 0.5rem;
  padding: 1.5rem;
  overflow-x: auto;
  color: #e2e8f0;
  font-family: monospace;
}
.nav-link {
  position: relative;
}
.nav-link::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  width: 0;
  height: 2px;
  background-color: #3b82f6;
  transition: width 0.3s ease;
}
.nav-link:hover::after {
  width: 100%;
}
</style>
<template>
  <div class="font-sans text-gray-800 antialiased" v-cloak>
    <div id="app">
      <!-- Navigation -->
      <nav class="bg-white shadow-md fixed w-full z-14">
        <div class="container mx-auto px-4 md:px-6 lg:px-8">
          <div class="flex justify-between items-center py-4">
            <div class="flex items-center">
              <img
                src="/GAMER.png"
                alt="Uzanet Logo"
                class="h-10 mr-3"
              />
            </div>

            <!-- Desktop Navigation -->
            <div class="hidden md:flex items-center space-x-8">
              <a
                href="#services"
                class="nav-link text-gray-700 hover:text-blue-600 font-medium transition duration-300"
                >Services</a
              >
              <a
                href="#how-it-works"
                class="nav-link text-gray-700 hover:text-blue-600 font-medium transition duration-300"
                >How It Works</a
              >
              <a
                href="#developer"
                class="nav-link text-gray-700 hover:text-blue-600 font-medium transition duration-300"
                >Developers</a
              >
              <a
                href="#pricing"
                class="nav-link text-gray-700 hover:text-blue-600 font-medium transition duration-300"
                >Pricing</a
              >
              <a
                href="#contact"
                class="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition duration-300"
                >Get Started</a
              >
            </div>

            <!-- Mobile Menu Button -->
            <div class="md:hidden flex items-center">
              <button
                @click="mobileMenuOpen = !mobileMenuOpen"
                class="text-gray-700 focus:outline-none"
              >
                <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    v-if="!mobileMenuOpen"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M4 6h16M4 12h16M4 18h16"
                  ></path>
                  <path
                    v-else
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M6 18L18 6M6 6l12 12"
                  ></path>
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Mobile Menu -->
        <div v-if="mobileMenuOpen" class="md:hidden bg-white shadow-lg py-2">
          <a
            href="#services"
            @click="mobileMenuOpen = false"
            class="block px-4 py-2 text-gray-700 hover:bg-blue-50"
            >Services</a
          >
          <a
            href="#how-it-works"
            @click="mobileMenuOpen = false"
            class="block px-4 py-2 text-gray-700 hover:bg-blue-50"
            >How It Works</a
          >
          <a
            href="#developer"
            @click="mobileMenuOpen = false"
            class="block px-4 py-2 text-gray-700 hover:bg-blue-50"
            >Developers</a
          >
          <a
            href="#pricing"
            @click="mobileMenuOpen = false"
            class="block px-4 py-2 text-gray-700 hover:bg-blue-50"
            >Pricing</a
          >
          <a
            href="#contact"
            @click="mobileMenuOpen = false"
            class="block px-4 py-2 text-blue-600 font-medium hover:bg-blue-50"
            >Get Started</a
          >
        </div>
      </nav>

      <!-- Hero Section -->
      <section class="relative overflow-hidden  pt-24 pb-16 md:pt-32 md:pb-24 bg-gradient-to-br from-blue-600 to-purple-600 text-white">
  <!-- Decorative animated blobs -->
  <div class="absolute top-0 left-0 w-72 h-72 bg-purple-500 opacity-30 rounded-full mix-blend-multiply filter blur-3xl animate-blob"></div>
  <div class="absolute bottom-0 right-0 w-96 h-96 bg-blue-300 opacity-20 rounded-full mix-blend-multiply filter blur-3xl animate-blob animation-delay-2000"></div>
  
  <div class="container mx-auto px-4 md:px-6 lg:px-8 relative z-10 flex flex-col-reverse md:flex-row items-center">
    <!-- Text Content -->
    <div class="md:w-1/2 space-y-6">
      <h1 class="text-4xl md:text-5xl font-extrabold leading-tight">
        Simplified 
        <span class="bg-clip-text text-transparent bg-gradient-to-r from-white to-purple-300">
          Internet Solutions.
        </span>
      </h1>
      <p class="text-lg md:text-xl text-gray-200">
        Cheap , Fast & Secure Solutions designed to elevate your digital experience. Join us in shaping the future of internet services in Africa.        
        
      </p>
      <div class="flex flex-col sm:flex-row gap-4">
        <a href="#services" class="inline-flex items-center justify-center bg-white text-blue-600 font-semibold py-3 px-6 rounded-lg shadow-lg hover:shadow-xl transition">
          Get Started
        </a>
        <a href="#developer" class="inline-flex items-center justify-center border-2 border-white text-white font-semibold py-3 px-6 rounded-lg hover:bg-white hover:text-blue-600 transition">
          Try API
        </a>
      </div>
      
    </div>

    <!-- Illustrative Media -->
    <div class="md:w-1/2 mb-10 md:mb-0 flex justify-center">
      <img 
        src="/1.svg" 
        alt="Abstract network illustration" 
        class="w-full max-w-md rounded-xl "
      />
    </div>

  </div>
  <!-- Feature Icons Row -->
  <div class="mt-24 px-4 md:px-6 lg:px-8 relative z-10">
    <div class="grid grid-cols-2 sm:grid-cols-3 gap-6">
      <!-- First row on mobile (2 items) -->
      <div class="flex flex-col items-center text-center space-y-2">
        <img class="w-16 h-16 sm:w-24 sm:h-24" src="/hotspot.svg" alt="ISP Billing Software"/>
        <span class="text-sm sm:text-base">ISP Billing Software</span>
      </div>
      <div class="flex flex-col items-center text-center space-y-2">
        <img class="w-16 h-16 sm:w-24 sm:h-24" src="/host.svg" alt="Web & Cloud Hosting"/>
        <span class="text-sm sm:text-base">Web & Cloud Hosting</span>
      </div>
      <!-- Second row on mobile (1 item), same row on desktop -->
      <div class="col-span-2 sm:col-span-1 flex flex-col items-center text-center space-y-2">
        <img class="w-16 h-16 sm:w-24 sm:h-24" src="/pro.svg" alt="API-as-a-Service"/>
        <span class="text-sm sm:text-base">API-as-a-Service</span>
      </div>
    </div>
  </div>
</section>

      <!-- Services Section -->
      <section id="services" class="py-24 bg-gray-50">
        <div class="container mx-auto px-4 md:px-6 lg:px-8">
          <TitleComponent
          image="/space.svg"
            title="Our Services"
            subtitle="Comprehensive solutions designed for everyone from small ISPs to large enterprises. Our services are tailored to meet the unique needs of your network, ensuring seamless connectivity and management."
          />


          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            <!-- Service Card 1 -->
            <div
              class="bg-white rounded-lg shadow-lg overflow-hidden transition duration-300 hover:shadow-xl"
            >
              <div class="p-6">
                <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
                  <i class="fas fa-server text-blue-600 text-xl"></i>
                </div>
                <h3 class="text-xl font-bold mb-2">ISP Software Suite</h3>
                <ul class="space-y-2 mb-4">
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Billing, package management, user provisioning (Hotspot & PPPoE).</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Real-time RX/TX monitoring.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>User management and access control.</span>
                  </li>
                </ul>
                <a href="#" class="text-blue-600 hover:text-blue-800 font-medium flex items-center">
                  Learn more
                  <svg
                    class="w-4 h-4 ml-1"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 5l7 7-7 7"
                    ></path>
                  </svg>
                </a>
              </div>
            </div>

            <!-- Service Card 2 -->
            <div
              class="bg-white rounded-lg shadow-lg overflow-hidden transition duration-300 hover:shadow-xl"
            >
              <div class="p-6">
                <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
                  <i class="fas fa-code text-blue-600 text-xl"></i>
                </div>
                <h3 class="text-xl font-bold mb-2">API as a Service</h3>
                <ul class="space-y-2 mb-4">
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Fully documented REST endpoints for payments, user management.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Logs and network statistics endpoints.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Instant onboarding.</span>
                  </li>
                </ul>
                <a href="#" class="text-blue-600 hover:text-blue-800 font-medium flex items-center">
                  Learn more
                  <svg
                    class="w-4 h-4 ml-1"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 5l7 7-7 7"
                    ></path>
                  </svg>
                </a>
              </div>
            </div>

            <!-- Service Card 3 -->
            <div
              class="bg-white rounded-lg shadow-lg overflow-hidden transition duration-300 hover:shadow-xl"
            >
              <div class="p-6">
                <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
                  <i class="fas fa-wifi text-blue-600 text-xl"></i>
                </div>
                <h3 class="text-xl font-bold mb-2">MikroTik & Access Point Sales</h3>
                <ul class="space-y-2 mb-4">
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Curated MikroTik routerboards & certified access points.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Volume pricing, global shipping.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Pre-configured hardware options available.</span>
                  </li>
                </ul>
                <a href="#" class="text-blue-600 hover:text-blue-800 font-medium flex items-center">
                  Learn more
                  <svg
                    class="w-4 h-4 ml-1"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 5l7 7-7 7"
                    ></path>
                  </svg>
                </a>
              </div>
            </div>

            <!-- Service Card 4 -->
            <div
              class="bg-white rounded-lg shadow-lg overflow-hidden transition duration-300 hover:shadow-xl"
            >
              <div class="p-6">
                <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
                  <i class="fas fa-palette text-blue-600 text-xl"></i>
                </div>
                <h3 class="text-xl font-bold mb-2">Hotspot Landing-Page Customization</h3>
                <ul class="space-y-2 mb-4">
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Custom hotspot login.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>payment intergrated login.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Mobile-responsive designs.</span>
                  </li>
                </ul>
                <a href="#" class="text-blue-600 hover:text-blue-800 font-medium flex items-center">
                  Learn more
                  <svg
                    class="w-4 h-4 ml-1"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 5l7 7-7 7"
                    ></path>
                  </svg>
                </a>
              </div>
            </div>

            <!-- Service Card 5 -->
            <div
              class="bg-white rounded-lg shadow-lg overflow-hidden transition duration-300 hover:shadow-xl"
            >
              <div class="p-6">
                <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
                  <i class="fas fa-ad text-blue-600 text-xl"></i>
                </div>
                <h3 class="text-xl font-bold mb-2">AD-Driven Free Wi-Fi</h3>
                <ul class="space-y-2 mb-4">
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Display targeted ads in exchange for free connectivity.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Seamless Microsoft AD/LDAP login support.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Detailed analytics and reporting.</span>
                  </li>
                </ul>
                <a href="#" class="text-blue-600 hover:text-blue-800 font-medium flex items-center">
                  Learn more
                  <svg
                    class="w-4 h-4 ml-1"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 5l7 7-7 7"
                    ></path>
                  </svg>
                </a>
              </div>
            </div>
            <!-- Service Card - Self Hosted Solutions -->
            <div class="bg-white rounded-lg shadow-lg overflow-hidden transition duration-300 hover:shadow-xl">
              <div class="p-6">
                <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
                  <i class="fas fa-server text-blue-600 text-xl"></i>
                </div>
                <h3 class="text-xl font-bold mb-2">Self-Hosted Solutions</h3>
                <ul class="space-y-2 mb-4">
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span><b>Vercel , AWS & Firebase alternatives :</b> </span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Coolify Virtual Private Servers.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Supabase self-hosted instances.</span>
                  </li>
                 
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Custom VPN server setup.</span>
                  </li>
                </ul>
                <a href="#" class="text-blue-600 hover:text-blue-800 font-medium flex items-center">
                  Learn more <svg class="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
                </a>
              </div>
            </div>

            <!-- Service Card - Enterprise Network Solutions -->
            <div class="bg-white rounded-lg shadow-lg overflow-hidden transition duration-300 hover:shadow-xl">
              <div class="p-6">
                <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
                  <i class="fas fa-network-wired text-blue-600 text-xl"></i>
                </div>
                <h3 class="text-xl font-bold mb-2">Enterprise Network Solutions</h3>
                <ul class="space-y-2 mb-4">
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Network setup and maintainance.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>IP CCTV system integration.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>IP Phone systems deployment.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Access control systems.</span>
                  </li>
                </ul>
                <a href="#" class="text-blue-600 hover:text-blue-800 font-medium flex items-center">
                  Learn more <svg class="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
                </a>
              </div>
            </div>

            <!-- Service Card - Web Services -->
            <div class="bg-white rounded-lg shadow-lg overflow-hidden transition duration-300 hover:shadow-xl">
              <div class="p-6">
                <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
                  <i class="fas fa-globe text-blue-600 text-xl"></i>
                </div>
                <h3 class="text-xl font-bold mb-2">Web Services</h3>
                <ul class="space-y-2 mb-4">
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Domain registration & hosting.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Free SSL certificates.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Website deployment services.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Custom virtual private servers.</span>
                  </li>
                </ul>
                <a href="#" class="text-blue-600 hover:text-blue-800 font-medium flex items-center">
                  Learn more <svg class="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
                </a>
              </div>
            </div>          
              <!-- Service Card - Blockchain Solutions -->
            <div class="bg-white rounded-lg shadow-lg overflow-hidden transition duration-300 hover:shadow-xl">
              <div class="p-6">
                <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
                  <i class="fas fa-cube text-blue-600 text-xl"></i>
                </div>
                <h3 class="text-xl font-bold mb-2">Blockchain Hosting Services</h3>
                <ul class="space-y-2 mb-4">
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Ethereum Staking Node Hosting.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Bitcoin Full Node Deployment.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>IPFS Node Configuration.</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Flux & Horizon Node Deployments.</span>
                  </li>

                </ul>
                <a href="#" class="text-blue-600 hover:text-blue-800 font-medium flex items-center">
                  Learn more <svg class="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
                </a>
              </div>
            </div>

            <!-- Service Card 6 - Empty for symmetry on larger screens, hidden on smaller -->
            <div
              class="bg-white rounded-lg shadow-lg overflow-hidden transition duration-300 hover:shadow-xl hidden lg:block"
            >
              <div class="p-6 flex items-center justify-center h-full">
                <div class="text-center">
                  <div
                    class="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4"
                  >
                    <i class="fas fa-plus text-blue-600 text-xl"></i>
                  </div>
                  <h3 class="text-xl font-bold mb-2">Custom Solutions</h3>
                  <p class="text-gray-600 mb-4">
                    Need something specific? Contact our team for custom network solutions tailored
                    to your needs.
                  </p>
                  <a
                    href="#contact"
                    class="inline-block bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition duration-300"
                    >Contact Us</a
                  >
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- How It Works Section -->
      <section id="how-it-works" class="py-24 bg-white">
        <div class="container mx-auto px-4 md:px-6 lg:px-8">
          
          <TitleComponent
          image="onboard.svg"
          title="How It Works"
          subtitle="Our onboarding process is designed to be quick and efficient, allowing you to focus on what matters most: your network."
        />

          <div class="flex flex-col md:flex-row justify-between items-center gap-8">
            <!-- Step 1 -->
            <div class="md:w-1/3 text-center">
              <div
                class="relative mx-auto w-24 h-24 bg-blue-100 rounded-full flex items-center justify-center mb-4"
              >
                <span class="text-blue-600 text-3xl font-bold">1</span>
                <div class="hidden md:block absolute top-12 right-0 w-full h-2 bg-blue-200"></div>
              </div>
              <h3 class="text-2xl font-bold mb-2">Sign Up</h3>
              <p class="text-gray-700">
                Create your Uzanet account in minutes with basic information about your network.
              </p>
            </div>

            <!-- Step 2 -->
            <div class="md:w-1/3 text-center">
              <div
                class="relative mx-auto w-24 h-24 bg-blue-100 rounded-full flex items-center justify-center mb-4"
              >
                <span class="text-blue-600 text-3xl font-bold">2</span>
                <div class="hidden md:block absolute top-12 right-0 w-full h-2 bg-blue-200"></div>
              </div>
              <h3 class="text-2xl font-bold mb-2">Provision</h3>
              <p class="text-gray-700">
                Set up your network credentials and receive your API keys for integration.
              </p>
            </div>

            <!-- Step 3 -->
            <div class="md:w-1/3 text-center">
              <div
                class="relative mx-auto w-24 h-24 bg-blue-100 rounded-full flex items-center justify-center mb-4"
              >
                <span class="text-blue-600 text-3xl font-bold">3</span>
              </div>
              <h3 class="text-2xl font-bold mb-2">Go Live</h3>
              <p class="text-gray-700">
                Launch your fully configured network with billing, monitoring, and management
                systems.
              </p>
            </div>
          </div>
        </div>
      </section>

      <!-- Developer Experience Section -->
      <section id="developer" class="py-24 bg-gray-50">
        <section class="px-4 md:px-6 lg:px-8">
          <TitleComponent
              
              image="/dev.svg"
              title="Developer Experience"
                subtitle="Our API is designed with developers in mind, providing a seamless experience for integration and customization. With comprehensive documentation, robust endpoints, and modern tooling support, you can build powerful network management solutions quickly and efficiently."
            />
        </section>
        <div class="container mx-auto px-4 md:px-6 lg:px-8">
          <div class="flex flex-col md:flex-row items-center gap-8">
            <div class="md:w-1/2">
             
             
                <div class="mb-8">
                <h3 class="text-xl font-bold mb-2">API Features:</h3>
                <ul class="space-y-2">
                  <li class="flex items-start">
                  <i class="fas fa-check-circle text-green-500 mt-1 mr-2"></i>
                  <span>RESTful endpoints for all network operations</span>
                  </li>
                  <li class="flex items-start">
                  <i class="fas fa-check-circle text-green-500 mt-1 mr-2"></i>
                  <span>Webhook support for real-time events</span>
                  </li>
                  <li class="flex items-start">
                  <i class="fas fa-check-circle text-green-500 mt-1 mr-2"></i>
                  <span>Comprehensive error handling</span>
                  </li>
                  <li class="flex items-start">
                  <i class="fas fa-check-circle text-green-500 mt-1 mr-2"></i>
                  <span>Rate limiting with clear headers</span>
                  </li>
                  <li class="flex items-start">
                  <i class="fas fa-check-circle text-green-500 mt-1 mr-2"></i>
                  <span>Lipa na M-PESA STK Push integration</span>
                  </li>
                  <li class="flex items-start">
                  <i class="fas fa-check-circle text-green-500 mt-1 mr-2"></i>
                  <span>KopoKopo payment gateway integration</span>
                  </li>
                  <li class="flex items-start">
                  <i class="fas fa-check-circle text-green-500 mt-1 mr-2"></i>
                  <span>Hotspot & PPPoE management endpoints</span>
                  </li>
                  <li class="flex items-start">
                  <i class="fas fa-check-circle text-green-500 mt-1 mr-2"></i>
                  <span>Paystack payment processing integration</span>
                  </li>
                  <li class="flex items-start">
                  <i class="fas fa-check-circle text-green-500 mt-1 mr-2"></i>
                  <span>Africa's Talking SMS/Voice API integration</span>
                  </li>
                </ul>
                </div>

              <a
                href="#"
                class="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-md inline-flex items-center transition duration-300"
              >
                <span>View API Documentation</span>
                <svg
                  class="w-4 h-4 ml-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                  ></path>
                </svg>
              </a>
            </div>

            <div class="w-full md:w-1/2">
              <div class="code-block">
                <pre>
// Fetch users example with Uzanet API
const UZANET_API_KEY = 'YOUR_API_KEY';

async function getNetworkUsers() {
  try {
    const response = await fetch(
      'https://api.uzanet.com/v1/users',
      {
        headers: {
          'Authorization': `Bearer ${UZANET_API_KEY}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const users = await response.json();
    console.log(`Found ${users.length} users`);
    return users;
  } catch (error) {
    console.error('Failed to fetch users:', error);
  }
}
</pre
                >
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Testimonials Section -->
      <section class="py-24 bg-white">
        <div class="container mx-auto px-4 md:px-6 lg:px-8">
          
          <TitleComponent
          image="/rev.svg"
            title="Customer Testimonials"
            subtitle="Our customers are at the heart of everything we do. Here’s what they have to say about their experience with Uzanet."
          />

          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            <!-- Testimonial 1 -->
            <div class="bg-gray-50 rounded-lg p-6 shadow-md">
              <div class="flex items-center mb-4">
                <div class="text-yellow-400 flex">
                  <i class="fas fa-star"></i>
                  <i class="fas fa-star"></i>
                  <i class="fas fa-star"></i>
                  <i class="fas fa-star"></i>
                  <i class="fas fa-star"></i>
                </div>
              </div>
              <p class="text-gray-700 italic mb-4">
                "Uzanet has transformed how we manage our network. The API integration was seamless
                and the customer support is outstanding."
              </p>
              <div class="flex items-center">
                <div class="w-12 h-12 bg-blue-200 rounded-full mr-4">
                  <img src="/paul.svg"/>
                </div>
                <div>
                  <h4 class="font-bold">Paul Kimani</h4>
                  <p class="text-sm text-gray-600">CTO, FastConnect ISP</p>
                </div>
              </div>
            </div>

            <!-- Testimonial 2 -->
            <div class="bg-gray-50 rounded-lg p-6 shadow-md">
              <div class="flex items-center mb-4">
                <div class="text-yellow-400 flex">
                  <i class="fas fa-star"></i>
                  <i class="fas fa-star"></i>
                  <i class="fas fa-star"></i>
                  <i class="fas fa-star"></i>
                  <i class="fas fa-star"></i>
                </div>
              </div>
              <p class="text-gray-700 italic mb-4">
                "The billing system integration saved us countless hours of manual work. Our
                customers love the self-service portal too."
              </p>
              <div class="flex items-center">
                <div class="w-12 h-12 bg-blue-200 rounded-full mr-4">
                  <img src="/fem.svg"/>
                </div>
                <div>
                  <h4 class="font-bold">Owner</h4>
                  <p class="text-sm text-gray-600">Tabitha Properties Hotspot</p>
                </div>
              </div>
            </div>

            <!-- Testimonial 3 -->
            <div class="bg-gray-50 rounded-lg p-6 shadow-md">
              <div class="flex items-center mb-4">
                <div class="text-yellow-400 flex">
                  <i class="fas fa-star"></i>
                  <i class="fas fa-star"></i>
                  <i class="fas fa-star"></i>
                  <i class="fas fa-star"></i>
                  <i class="fas fa-star-half-alt"></i>
                </div>
              </div>
              <p class="text-gray-700 italic mb-4">
                "As a small ISP, Uzanet gave us enterprise-level tools at a price we could afford.
                The MikroTik integration is flawless."
              </p>
              <div class="flex items-center">
                <div class="w-12 h-12 bg-blue-200 rounded-full mr-4">
                  <img src="/paul.svg"/>
                </div>
                <div>
                  <h4 class="font-bold">David Chen</h4>
                  <p class="text-sm text-gray-600">Network Admin, LocalNet</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Partner Logos -->
          <div class="mt-16">
            <TitleComponent
              image="/part.svg"
              title="Partners & Integrations"
              subtitle="We collaborate with leading technology providers to deliver the best solutions for our customers.From payment gateways to hardware vendors, our partners help us ensure a seamless experience."
            />
            <div class="flex flex-wrap justify-center items-center gap-8 md:gap-12">
              <img class="w-42 h-24 flex items-center justify-center" src="/MikroTik_logo_PNG_(4).png"></img>
              <img class="w-42 h-24 flex items-center justify-center" src="/MicrosoftTeams-image_41.png"></img>
              <img class="w-42 h-24 flex items-center justify-center" src="/pay.jpeg"></img>

              <img class="w-42 h-24 flex items-center justify-center" src="/kopo.png"></img>

              <img class="w-42 h-24 flex items-center justify-center" src="/talking.png"></img>
              <img class="w-42 h-24 flex items-center justify-center" src="/starlink.jpeg"></img>
              <img class="w-42 h-24 flex items-center justify-center" src="/ubi.jpeg"></img>
              <img class="w-42 h-24 flex items-center justify-center" src="/tenda.jpeg"></img>
              <img class="w-42 h-24 flex items-center justify-center" src="/wire.jpg"></img>
              

            </div>
          </div>
        </div>
      </section>
      <!-- Pricing Section -->
      <section id="pricing" class="py-24 bg-gray-50">
        <div class="container mx-auto px-4 md:px-6 lg:px-8">
          <div class="text-center mb-12">
            
            <TitleComponent
              image="/pay.svg"
              title="Pricing Plans"
              subtitle="Whether you're a small startup or a large enterprise, we have a plan for you. All plans include access to our API, support, and regular updates."
            />
            <h3 class="text-2xl font-bold text-center mb-8">Wifi Billing Software</h3>

          </div>
          

          <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
            <!-- Starter Plan -->
            <div
              class="bg-white rounded-lg shadow-lg overflow-hidden transition duration-300 hover:shadow-xl"
            >
              <div class="p-6">
                <h3 class="text-2xl font-bold mb-2">Starter</h3>
                <div class="flex items-baseline mb-4">
                  <span class="text-4xl font-bold">$9.99</span>
                  <span class="text-gray-600 ml-1">/month</span>
                </div>
                <p class="text-gray-600 mb-6">Perfect for small networks and startups</p>
                <ul class="space-y-3 mb-6">
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Up to 50 users</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Basic billing system</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>1,000 API calls per day</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Basic hotspot templates</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Email support</span>
                  </li>
                </ul>
                <a
                  href="#contact"
                  class="block w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-md text-center transition duration-300"
                  >Get Started</a
                >
              </div>
            </div>

            <!-- Pro Plan -->
            <div
              class="bg-white rounded-lg shadow-xl overflow-hidden border-2 border-blue-600 transform md:-translate-y-4 transition duration-300 hover:shadow-2xl"
            >
              <div class="bg-blue-600 py-2">
                <p class="text-white text-center font-medium">Most Popular</p>
              </div>
              <div class="p-6">
                <h3 class="text-2xl font-bold mb-2">Professional</h3>
                <div class="flex items-baseline mb-4">
                  <span class="text-4xl font-bold">$24.99</span>
                  <span class="text-gray-600 ml-1">/month</span>
                </div>
                <p class="text-gray-600 mb-6">For growing networks with advanced needs</p>
                <ul class="space-y-3 mb-6">
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Up to 250 users</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Advanced billing & invoicing</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>5,000 API calls per day</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Advanced hotspot customization</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Priority support</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>AD-driven WiFi capabilities</span>
                  </li>
                </ul>
                <a
                  href="#contact"
                  class="block w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-md text-center transition duration-300"
                  >Get Started</a
                >
              </div>
            </div>

            <!-- Enterprise Plan -->
            <div
              class="bg-white rounded-lg shadow-lg overflow-hidden transition duration-300 hover:shadow-xl"
            >
              <div class="p-6">
                <h3 class="text-2xl font-bold mb-2">Enterprise</h3>
                <div class="flex items-baseline mb-4">
                  <span class="text-4xl font-bold">$59.99</span>
                  <span class="text-gray-600 ml-1">/month</span>
                </div>
                <p class="text-gray-600 mb-6">For large ISPs with complex requirements</p>
                <ul class="space-y-3 mb-6">
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Unlimited users</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Complete financial suite</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Unlimited API calls</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>Custom hotspot development</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>24/7 dedicated support</span>
                  </li>
                  <li class="flex items-start">
                    <i class="fas fa-check text-green-500 mt-1 mr-2"></i>
                    <span>White-label options</span>
                  </li>
                </ul>
                <a
                  href="#contact"
                  class="block w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-md text-center transition duration-300"
                  >Contact Sales</a
                >
              </div>
            </div>
          </div>

          <!-- Hardware Pricing -->
          <div class="mt-16">
            <h3 class="text-2xl font-bold text-center mb-8">Hardware Bundles</h3>
            <div class="bg-white rounded-lg shadow-lg p-6 md:p-8">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                <!-- Starter Bundle -->
                <div
                  class="border-b md:border-b-0 md:border-r border-gray-200 pb-6 md:pb-0 md:pr-8"
                >
                  <h4 class="text-xl font-bold mb-4">Starter Bundle</h4>
                  <p class="text-gray-700 mb-4">Perfect for small office or café hotspots.</p>
                  <div class="flex items-center mb-4">
                    <img
                      src="/rout.jpeg"
                      alt="MikroTik Router"
                      class="w-16 h-16 object-cover rounded-md mr-4"
                    />
                    <div>
                      <h5 class="font-bold">Mikrotik RB951Ui</h5>
                      <p class="text-sm text-gray-600">
                        Dual-band home AP with five Ethernet ports
                      </p>
                    </div>
                  </div>
                  <div class="flex items-center mb-6">
                    <img
                      src="/tp.jpeg"
                      alt="Access Point"
                      class="w-16 h-16 object-cover rounded-md mr-4"
                    />
                    <div>
                      <h5 class="font-bold">2× Access Points</h5>
                      <p class="text-sm text-gray-600">Indoor/outdoor options available</p>
                    </div>
                  </div>
                  <div class="flex items-baseline mb-6">
                    <span class="text-2xl font-bold">$200</span>
                    <span class="text-gray-600 ml-1">one-time</span>
                  </div>
                  <a
                    href="#"
                    class="text-blue-600 hover:text-blue-800 font-medium flex items-center"
                  >
                    Learn more
                    <svg
                      class="w-4 h-4 ml-1"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M9 5l7 7-7 7"
                      ></path>
                    </svg>
                  </a>
                </div>

                <!-- Pro Bundle -->
                <div class="pt-6 md:pt-0 md:pl-8">
                  <h4 class="text-xl font-bold mb-4">Professional Bundle</h4>
                  <p class="text-gray-700 mb-4">For multi-site deployments and larger networks.</p>
                  <div class="flex items-center mb-4">
                    <img
                      src="/rout.png"
                      alt="MikroTik Router"  
                      class="w-16 h-16 object-cover rounded-md mr-4"
                    />
                    <div>
                      <h5 class="font-bold">L009UiGS-2HaxD-IN

                      </h5>
                      <p class="text-sm text-gray-600">Cloud Core Router with high throughput</p>
                    </div>
                  </div>
                  <div class="flex items-center mb-6">
                    <img
                      src="/acc.jpg"
                      alt="Access Point"
                      class="w-16 h-16 object-cover rounded-md mr-4"
                    />
                    <div>
                      <h5 class="font-bold">4× Enterprise APs</h5>
                      <p class="text-sm text-gray-600">High-density coverage for businesses</p>
                    </div>
                  </div>
                  <div class="flex items-baseline mb-6">
                    <span class="text-2xl font-bold">$899</span>
                    <span class="text-gray-600 ml-1">one-time</span>
                  </div>
                  <a
                    href="#"
                    class="text-blue-600 hover:text-blue-800 font-medium flex items-center"
                  >
                    Learn more
                    <svg
                      class="w-4 h-4 ml-1"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M9 5l7 7-7 7"
                      ></path>
                    </svg>
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Call to Action Section 
      <section id="contact" class="py-16 gradient-bg text-white">
        <div class="container mx-auto px-4 md:px-6 lg:px-8">
          <div class="max-w-3xl mx-auto text-center">
            <h2 class="text-3xl md:text-4xl font-bold mb-4">Ready to Power Your Network?</h2>
            <p class="text-xl text-gray-200 mb-8">
              Get started with Uzanet today and transform how you manage your ISP business.
            </p>
            <div class="flex flex-col sm:flex-row justify-center gap-4">
              <a
                href="#"
                class="bg-white text-blue-600 hover:bg-gray-100 font-bold py-3 px-8 rounded-md text-center transition duration-300"
                >Start Free Trial</a
              >
              <a
                href="#"
                class="bg-transparent hover:bg-white hover:text-blue-600 text-white font-bold py-3 px-8 border-2 border-white rounded-md text-center transition duration-300"
                >Contact Sales</a
              >
            </div>
            <p class="mt-6 text-gray-300">No credit card required. 14-day free trial.</p>
          </div>
        </div>
      </section>-->

      <!-- Footer -->
      <footer class="bg-gray-800 text-gray-300 py-12">
        <div class="container mx-auto px-4 md:px-6 lg:px-8">
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <!-- Company Info -->
            <div>
              <h4 class="text-xl font-bold text-white mb-4">Uzanet</h4>
              <p class="mb-4">
                All-in-one ISP software, API-as-a-Service, and hardware solutions for modern network
                operators.
              </p>
              <div class="flex space-x-4">
                <a href="#" class="text-gray-400 hover:text-white transition duration-300">
                  <i class="fab fa-linkedin text-xl"></i>
                </a>
                <a href="#" class="text-gray-400 hover:text-white transition duration-300">
                  <i class="fab fa-twitter text-xl"></i>
                </a>
                <a href="#" class="text-gray-400 hover:text-white transition duration-300">
                  <i class="fab fa-github text-xl"></i>
                </a>
              </div>
            </div>

            <!-- Resources -->
            <div>
              <h4 class="text-white font-bold mb-4">Resources</h4>
              <ul class="space-y-2">
                <li>
                  <a href="#" class="text-gray-400 hover:text-white transition duration-300"
                    >Documentation</a
                  >
                </li>
                <li>
                  <a href="#" class="text-gray-400 hover:text-white transition duration-300"
                    >API Reference</a
                  >
                </li>
                <li>
                  <a href="#" class="text-gray-400 hover:text-white transition duration-300"
                    >Tutorials</a
                  >
                </li>
                <li>
                  <a href="#" class="text-gray-400 hover:text-white transition duration-300"
                    >Blog</a
                  >
                </li>
              </ul>
            </div>

            <!-- Company -->
            <div>
              <h4 class="text-white font-bold mb-4">Company</h4>
              <ul class="space-y-2">
                <li>
                  <a href="#" class="text-gray-400 hover:text-white transition duration-300"
                    >About Us</a
                  >
                </li>
                <li>
                  <a href="#" class="text-gray-400 hover:text-white transition duration-300"
                    >Careers</a
                  >
                </li>
                <li>
                  <a href="#" class="text-gray-400 hover:text-white transition duration-300"
                    >Partners</a
                  >
                </li>
                <li>
                  <a href="#" class="text-gray-400 hover:text-white transition duration-300"
                    >Contact</a
                  >
                </li>
              </ul>
            </div>

            <!-- Legal -->
            <div>
              <h4 class="text-white font-bold mb-4">Legal</h4>
              <ul class="space-y-2">
                <li>
                  <a href="#" class="text-gray-400 hover:text-white transition duration-300"
                    >Privacy Policy</a
                  >
                </li>
                <li>
                  <a href="#" class="text-gray-400 hover:text-white transition duration-300"
                    >Terms of Service</a
                  >
                </li>
                <li>
                  <a href="#" class="text-gray-400 hover:text-white transition duration-300"
                    >Data Processing</a
                  >
                </li>
                <li>
                  <a href="#" class="text-gray-400 hover:text-white transition duration-300"
                    >Cookie Policy</a
                  >
                </li>
              </ul>
            </div>
          </div>

          <div
            class="border-t border-gray-700 mt-8 pt-8 flex flex-col md:flex-row justify-between items-center"
          >
            <p>© 2025 Uzanet. All rights reserved.</p>
            <div class="mt-4 md:mt-0">
              <select class="bg-gray-700 text-gray-300 rounded-md py-1 px-2">
                <option value="en">English</option>
                <option value="es">Español</option>
                <option value="fr">Français</option>
              </select>
            </div>
          </div>
        </div>
      </footer>
    </div>
  </div>
</template>
