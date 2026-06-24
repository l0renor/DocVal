<script setup>
import ResultCard from '@/components/ResultCard.vue'

defineProps({
  results: { type: Array, default: () => [] },
})
</script>

<template>
  <div class="d-flex flex-column ga-4">
    <ResultCard v-for="(result, index) in results" :key="index" :result="result" />
  </div>
</template>
