<script setup>
import ResultCard from '@/components/ResultCard.vue'

defineProps({
  results: { type: Array, default: () => [] },
})
</script>

<template>
  <div>
    <div class="d-flex align-center ga-2 mb-4">
      <v-icon icon="mdi-clipboard-check-outline" color="primary" />
      <h2 class="text-h6">Prüfergebnis</h2>
      <v-chip size="small" variant="tonal" color="primary">
        {{ results.length }} {{ results.length === 1 ? 'Dokument' : 'Dokumente' }}
      </v-chip>
    </div>

    <div class="d-flex flex-column ga-6">
      <ResultCard v-for="(result, index) in results" :key="index" :result="result" />
    </div>
  </div>
</template>
