<script setup>
import { computed } from 'vue'
import StatusAmpel from '@/components/StatusAmpel.vue'
import ExtractedFieldsTable from '@/components/ExtractedFieldsTable.vue'
import DeficiencyList from '@/components/DeficiencyList.vue'

const props = defineProps({
  result: { type: Object, required: true },
})

const confidencePct = computed(() => Math.round((props.result.confidence ?? 0) * 100))
</script>

<template>
  <v-card class="result-card" variant="elevated" elevation="2" data-testid="result-card">
    <v-card-item class="bg-surface-light">
      <template #prepend>
        <v-avatar color="primary" variant="tonal" rounded="lg">
          <v-icon icon="mdi-file-document-outline" />
        </v-avatar>
      </template>
      <v-card-title>{{ result.classification.document_type }}</v-card-title>
      <v-card-subtitle>Erkannter Dokumenttyp</v-card-subtitle>
      <template #append>
        <StatusAmpel :status="result.validation_status" />
      </template>
    </v-card-item>

    <v-divider />

    <v-card-text>
      <div class="d-flex align-center mb-4 ga-3">
        <v-icon icon="mdi-gauge" size="small" color="secondary" />
        <span class="text-caption text-medium-emphasis">Lesbarkeitswert</span>
        <v-progress-linear
          :model-value="confidencePct"
          color="primary"
          height="8"
          rounded
          class="flex-grow-1"
        />
        <span class="text-body-2 font-weight-medium">{{ confidencePct }}%</span>
      </div>

      <h4 class="text-subtitle-1 font-weight-bold mb-2">Extrahierte Daten</h4>
      <ExtractedFieldsTable :fields="result.extracted_data" />

      <h4 class="text-subtitle-1 font-weight-bold mt-6 mb-2">Mängel</h4>
      <DeficiencyList :deficiencies="result.deficiencies" />

      <v-alert
        v-if="result.internal_note"
        class="mt-6"
        type="info"
        variant="tonal"
        icon="mdi-information-outline"
        title="Hinweis"
        :text="result.internal_note"
      />
    </v-card-text>
  </v-card>
</template>
