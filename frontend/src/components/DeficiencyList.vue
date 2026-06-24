<script setup>
defineProps({
  deficiencies: { type: Array, default: () => [] },
})
</script>

<template>
  <v-list v-if="deficiencies.length" class="py-0" bg-color="transparent">
    <v-list-item
      v-for="(deficiency, index) in deficiencies"
      :key="index"
      class="px-3 mb-2 rounded-lg deficiency-item"
      :title="deficiency.field"
      :subtitle="deficiency.reason"
      lines="two"
    >
      <template #prepend>
        <v-icon color="error" icon="mdi-alert-circle" class="me-1" />
      </template>
    </v-list-item>
  </v-list>

  <v-alert
    v-else
    type="success"
    variant="tonal"
    density="compact"
    icon="mdi-check-circle"
    title="Keine Mängel"
  />
</template>

<style scoped>
.deficiency-item {
  background-color: rgba(198, 40, 40, 0.06);
}
</style>
