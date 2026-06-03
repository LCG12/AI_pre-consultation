<script setup>
import { ref, watch } from 'vue'
import { getDoctorSummary } from '../api.js'

const props = defineProps({ sessionId: String, completed: Boolean })
const summary = ref(null)
const loading = ref(false)

watch(() => props.completed, (v) => { if (!v) summary.value = null })

async function load() {
  loading.value = true
  try {
    summary.value = await getDoctorSummary(props.sessionId)
  } catch (e) {
    alert('生成失败: ' + e.message)
  }
  loading.value = false
}
</script>

<template>
  <div class="summary-panel">
    <div class="panel-title">医生摘要</div>
    <div class="content" v-if="completed">
      <button class="btn primary" @click="load" :disabled="loading">
        {{ loading ? '生成中...' : '生成摘要' }}
      </button>
      <div v-if="summary" class="result">
        <div class="item" v-for="(v, k) in summary.summary" :key="k">
          <div class="k">{{ k }}</div>
          <div class="v">{{ Array.isArray(v) ? v.join('；') : v }}</div>
        </div>
        <div class="dept" v-if="summary.recommended_departments?.length">
          推荐科室：{{ summary.recommended_departments.join('、') }}
        </div>
      </div>
    </div>
    <div v-else class="hint">会话完成后可生成</div>
  </div>
</template>

<style scoped>
.summary-panel { border-top: 1px solid #e0e0e0; background: #fff; max-height: 280px; display: flex; flex-direction: column; }
.panel-title { padding: 10px 16px; font-size: 13px; font-weight: 600; color: #555; border-bottom: 1px solid #eee; }
.content { padding: 12px 16px; overflow-y: auto; flex: 1; }
.hint { padding: 16px; text-align: center; color: #ccc; font-size: 13px; }

.result { margin-top: 10px; }
.item { margin-bottom: 8px; }
.k { font-size: 11px; color: #999; }
.v { font-size: 13px; color: #333; margin-top: 2px; }
.dept { margin-top: 10px; padding-top: 8px; border-top: 1px solid #eee; font-size: 13px; color: #1a73e8; }

.btn { padding: 7px 14px; border: none; border-radius: 4px; font-size: 13px; cursor: pointer; }
.btn:disabled { opacity: 0.5; }
.btn.primary { background: #1a73e8; color: #fff; }
</style>
