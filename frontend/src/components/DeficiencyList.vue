<script setup>
defineProps({
  deficiencies: { type: Array, default: () => [] },
})
</script>

<template>
  <v-list v-if="deficiencies.length" density="compact">
    <v-list-item
      v-for="(deficiency, index) in deficiencies"
      :key="index"
      :title="deficiency.field"
      :subtitle="deficiency.reason"
    >
      <template #prepend>
        <v-icon color="red" icon="mdi-alert-circle" />
      </template>
    </v-list-item>
  </v-list>
  <p v-else class="text-medium-emphasis">Keine Mängel</p>
</template>
