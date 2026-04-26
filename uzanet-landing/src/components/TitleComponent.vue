<template>
  <section
    class="flex flex-col-reverse md:flex-row items-center rounded-2xl p-8 md:p-16 overflow-hidden"
  >
    <!-- Text Content -->
    <div class="md:w-1/2 text-center md:text-left">
      <h2
        class="text-3xl md:text-4xl font-extrabold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-blue-800 to-purple-600 drop-shadow-md"
      >
        {{ props.title }}
      </h2>
      <p class="text-lg md:text-xl text-black max-w-xl mx-auto md:mx-0 leading-relaxed">
        {{ props.subtitle }}
      </p>
    </div>
    <!-- Illustration -->
    <div class="md:w-1/2 flex justify-center mb-6 md:mb-0">
      <img :src="props.image" alt="Our Services Illustration" class="w-3/4 h-auto" />
    </div>
  </section>
</template>
<script setup>
import { ref, defineProps } from 'vue'

const title = ref('')
const subtitle = ref('')
const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  subtitle: {
    type: String,
    required: true,
  },
  image: {
    type: String,
    required: true,
  },
})
</script>
