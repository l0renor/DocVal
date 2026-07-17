<script setup>
import { computed } from 'vue'

const props = defineProps({
  metadata: { type: Object, required: true },
})

const statusConfig = computed(() => {
  if (props.metadata.antrag_status === 'accepted') {
    return { color: 'success', icon: 'mdi-check-circle', label: 'Antrag vollständig' }
  }
  return { color: 'warning', icon: 'mdi-alert-circle', label: 'Antrag unvollständig' }
})
</script>

<template>
  <v-card variant="elevated" elevation="2" class="mb-4">
    <v-card-item>
      <template #prepend>
        <v-icon :icon="statusConfig.icon" :color="statusConfig.color" />
      </template>
      <v-card-title class="text-h6">Antrag-Gesamtergebnis</v-card-title>
    </v-card-item>

    <v-card-text>
      <!-- Bundle status chip -->
      <v-chip
        :color="statusConfig.color"
        variant="tonal"
        class="mb-3"
        :data-antrag-status="metadata.antrag_status"
      >
        <v-icon start :icon="statusConfig.icon" />
        {{ statusConfig.label }}
      </v-chip>

      <!-- German summary -->
      <p v-if="metadata.summary" class="text-body-2 mb-3">{{ metadata.summary }}</p>

      <!-- Cross-document findings -->
      <template v-if="metadata.cross_document_findings?.length">
        <p class="text-subtitle-2 font-weight-bold mb-1">Dokumentübergreifende Befunde</p>
        <v-list density="compact" class="mb-3 pa-0">
          <v-list-item
            v-for="(finding, i) in metadata.cross_document_findings"
            :key="i"
            :title="finding"
            prepend-icon="mdi-alert-circle-outline"
            base-color="error"
          />
        </v-list>
      </template>

      <!-- Missing required documents -->
      <template v-if="metadata.missing_required_documents?.length">
        <p class="text-subtitle-2 font-weight-bold mb-1">Fehlende Pflichtdokumente</p>
        <v-list density="compact" class="pa-0">
          <v-list-item
            v-for="(doc, i) in metadata.missing_required_documents"
            :key="i"
            :title="doc"
            prepend-icon="mdi-file-remove-outline"
            base-color="error"
          />
        </v-list>
      </template>
    </v-card-text>
  </v-card>
</template>
