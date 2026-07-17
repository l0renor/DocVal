<script setup>
import { ref, computed } from 'vue'
import { submitDocument } from '@/api/docverify.js'
import ResultsList from '@/components/ResultsList.vue'
import DocumentPreview from '@/components/DocumentPreview.vue'
import AntragsMetadataCard from '@/components/AntragsMetadataCard.vue'

const EXAMPLE_CONFIG = JSON.stringify(
  {
    document_types: [
      { id: 'personalausweis', description: 'Personalausweis', required: true },
      { id: 'mietvertrag', description: 'Mietvertrag', required: false },
    ],
  },
  null,
  2,
)

const props = defineProps({
  baseUrl: { type: String, default: '/api' },
  // Injectable for tests; called with { files, submissionType, config }.
  submitFn: { type: Function, default: null },
})

const mode = ref('dokument') // 'dokument' | 'antrag'
const selectedFiles = ref([])
const configJson = ref(EXAMPLE_CONFIG)
const status = ref('idle') // idle | loading | done | error
const results = ref([])
const antragMetadata = ref(null)
const errorMessage = ref('')

const isAntrag = computed(() => mode.value === 'antrag')

const internalSubmit = props.submitFn
  || (({ files, submissionType, config }) =>
    submitDocument({ files, submissionType, config }, { baseUrl: props.baseUrl }))

async function onFileSelected(value) {
  const files = Array.isArray(value) ? value : (value ? [value] : [])
  if (!files.length) return
  selectedFiles.value = files
  status.value = 'loading'
  errorMessage.value = ''
  results.value = []
  antragMetadata.value = null
  try {
    const config = configJson.value.trim() || null
    const response = await internalSubmit({
      files,
      submissionType: mode.value,
      config,
    })
    results.value = response.results
    antragMetadata.value = response.antragMetadata ?? null
    status.value = 'done'
  } catch (err) {
    errorMessage.value = err.message || 'Unbekannter Fehler'
    status.value = 'error'
  }
}

function loadConfigFromFile(event) {
  const file = event.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (e) => {
    configJson.value = e.target.result
  }
  reader.readAsText(file)
}
</script>

<template>
  <v-app>
    <v-app-bar color="primary" flat>
      <template #prepend>
        <v-icon icon="mdi-file-document-check-outline" class="ms-2" />
      </template>
      <v-app-bar-title class="font-weight-bold">DocVerify</v-app-bar-title>
      <template #append>
        <span class="text-caption text-medium-emphasis me-4 d-none d-sm-inline">
          Prüf- und Extraktionsassistent
        </span>
      </template>
    </v-app-bar>

    <v-main class="bg-background">
      <v-container class="py-8">
        <v-row>
          <!-- Left: controls + preview -->
          <v-col cols="12" md="5">
            <v-card variant="elevated" elevation="2">
              <v-card-item>
                <template #prepend>
                  <v-icon icon="mdi-tray-arrow-up" color="primary" />
                </template>
                <v-card-title class="text-h6">Dokument prüfen</v-card-title>
                <v-card-subtitle>PDF, PNG oder JPG hochladen</v-card-subtitle>
              </v-card-item>

              <v-card-text>
                <!-- Mode toggle -->
                <v-btn-toggle
                  v-model="mode"
                  mandatory
                  rounded="lg"
                  color="primary"
                  class="mb-4"
                  density="comfortable"
                >
                  <v-btn value="dokument">Dokument</v-btn>
                  <v-btn value="antrag">Antrag</v-btn>
                </v-btn-toggle>

                <!-- File upload (multiple for antrag) -->
                <v-file-input
                  label="Dokument auswählen"
                  accept="application/pdf,image/png,image/jpeg"
                  prepend-icon="mdi-paperclip"
                  :loading="status === 'loading'"
                  :disabled="status === 'loading'"
                  :multiple="isAntrag"
                  show-size
                  clearable
                  @update:model-value="onFileSelected"
                />

                <!-- Config editor -->
                <v-textarea
                  v-model="configJson"
                  label="Konfiguration (JSON)"
                  rows="8"
                  variant="outlined"
                  density="compact"
                  class="mt-2 font-weight-regular"
                  style="font-family: monospace; font-size: 12px"
                  :disabled="status === 'loading'"
                />

                <!-- Load config from file -->
                <v-btn
                  variant="tonal"
                  size="small"
                  prepend-icon="mdi-folder-open-outline"
                  class="mt-1"
                  :disabled="status === 'loading'"
                  @click="$refs.configFileInput.click()"
                >
                  Aus Datei laden
                </v-btn>
                <input
                  ref="configFileInput"
                  type="file"
                  accept="application/json,.json"
                  class="d-none"
                  @change="loadConfigFromFile"
                />
              </v-card-text>
            </v-card>

            <div class="mt-4">
              <DocumentPreview :file="selectedFiles[0] ?? null" />
            </div>
          </v-col>

          <!-- Right: results / states -->
          <v-col cols="12" md="7">
            <v-fade-transition mode="out-in">
              <div v-if="status === 'loading'" key="loading">
                <div class="d-flex align-center ga-3 mb-4">
                  <v-progress-circular indeterminate color="primary" size="24" />
                  <span class="text-body-1">Dokument wird geprüft …</span>
                </div>
                <v-skeleton-loader type="article, table" />
              </div>

              <v-alert
                v-else-if="status === 'error'"
                key="error"
                type="error"
                variant="tonal"
                prominent
                icon="mdi-alert-octagon"
                title="Prüfung fehlgeschlagen"
                :text="errorMessage"
              />

              <div v-else-if="status === 'done'" key="done">
                <!-- Antrag bundle metadata appears above per-document results -->
                <AntragsMetadataCard
                  v-if="antragMetadata"
                  :metadata="antragMetadata"
                />
                <ResultsList :results="results" />
              </div>

              <v-sheet
                v-else
                key="empty"
                rounded="lg"
                border
                class="d-flex flex-column align-center justify-center text-medium-emphasis pa-12 text-center"
                min-height="320"
              >
                <v-icon icon="mdi-file-search-outline" size="64" class="mb-4" />
                <p class="text-body-1">
                  Noch kein Dokument geprüft — bitte ein Dokument auswählen.
                </p>
              </v-sheet>
            </v-fade-transition>
          </v-col>
        </v-row>
      </v-container>
    </v-main>
  </v-app>
</template>
