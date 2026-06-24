<script setup>
import StatusAmpel from '@/components/StatusAmpel.vue'
import ExtractedFieldsTable from '@/components/ExtractedFieldsTable.vue'
import DeficiencyList from '@/components/DeficiencyList.vue'

defineProps({
  result: { type: Object, required: true },
})
</script>

<template>
  <v-card class="result-card" variant="outlined" data-testid="result-card">
    <v-card-item>
      <div class="d-flex align-center justify-space-between">
        <v-card-title>{{ result.classification.document_type }}</v-card-title>
        <StatusAmpel :status="result.validation_status" />
      </div>
    </v-card-item>

    <v-card-text>
      <ExtractedFieldsTable :fields="result.extracted_data" />

      <h4 class="mt-4 mb-1">Mängel</h4>
      <DeficiencyList :deficiencies="result.deficiencies" />

      <v-alert
        v-if="result.internal_note"
        class="mt-4"
        type="info"
        variant="tonal"
        title="Hinweis"
        :text="result.internal_note"
      />
    </v-card-text>
  </v-card>
</template>
