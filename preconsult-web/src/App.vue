<script setup>
import { ref, computed } from 'vue'
import { fetchPaths, createSession, getResult } from './api.js'
import ChatPanel from './components/ChatPanel.vue'
import StatePanel from './components/StatePanel.vue'
import SummaryPanel from './components/SummaryPanel.vue'
import SessionList from './components/SessionList.vue'

const paths = ref([])
const selectedPath = ref('')
const sessionId = ref(null)
const state = ref({ slots: {} })
const departments = ref([])
const completed = computed(() => state.value.status === 'completed' || state.value.status === 'emergency')
const sessionListRef = ref(null)

async function loadPaths() {
  try { paths.value = await fetchPaths() } catch (e) { /* */ }
}
loadPaths()

async function handleCreate() {
  if (!selectedPath.value) return
  const data = await createSession(selectedPath.value)
  sessionId.value = data.session_id
  state.value = { session_id: data.session_id, status: data.status, risk: { current_level: data.risk_level }, path_id: selectedPath.value, slots: {}, dialogue: { turn_count: 0 } }
  departments.value = []
  sessionListRef.value?.refresh()
}

async function handleSelectSession(sid) {
  sessionId.value = sid
  try {
    const s = await getResult(sid)
    state.value = s
  } catch (e) { /* */ }
}

function handleReset() {
  sessionId.value = null
  state.value = { slots: {} }
  selectedPath.value = ''
  sessionListRef.value?.refresh()
}

function onStateUpdate(s, deps) {
  state.value = s
  if (deps) departments.value = deps
}
</script>

<template>
  <div class="app">
    <header class="header">
      <h1>AI 预问诊系统</h1>
      <span class="sub">DeepSeek · 智能追问 · 医生摘要</span>
    </header>

    <div class="toolbar">
      <select v-model="selectedPath">
        <option value="">-- 选择问诊路径 --</option>
        <option v-for="p in paths" :key="p.id" :value="p.id">{{ p.name }}</option>
      </select>
      <button class="btn primary" @click="handleCreate" :disabled="!selectedPath">新建会话</button>
      <button class="btn danger" @click="handleReset" :disabled="!sessionId">重置</button>
      <span class="info">会话: {{ sessionId || '-' }}</span>
      <span class="info">状态: {{ state.status || '-' }}</span>
      <span class="info">风险: <b :class="'risk-' + (state.risk?.current_level || 'unknown')">{{ riskLabel(state.risk?.current_level) }}</b></span>
      <span class="info">路径: {{ pathLabel }}</span>
    </div>

    <div class="main">
      <SessionList ref="sessionListRef" :currentId="sessionId" @select="handleSelectSession" />
      <ChatPanel
        :sessionId="sessionId"
        :state="state"
        :completed="completed"
        @stateUpdate="onStateUpdate"
      />
      <div class="right">
        <StatePanel :state="state" :departments="departments" />
        <SummaryPanel :sessionId="sessionId" :completed="completed" />
      </div>
    </div>
  </div>
</template>

<script>
export default {
  computed: {
    pathLabel() {
      const p = this.paths.find(p => p.id === this.state.path_id)
      return p ? p.name : (this.state.path_id || '-')
    }
  },
  methods: {
    riskLabel(level) {
      const m = { unknown: '未知', green: '绿色', yellow: '黄色', red: '红色' }
      return m[level] || '-'
    }
  }
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f0f2f5; }
.app { display: flex; flex-direction: column; height: 100vh; }

.header { background: linear-gradient(135deg, #1a73e8, #0d47a1); color: #fff; padding: 10px 24px; display: flex; align-items: center; gap: 12px; }
.header h1 { font-size: 18px; }
.header .sub { font-size: 12px; opacity: 0.8; }

.toolbar { background: #fff; padding: 8px 24px; display: flex; gap: 10px; align-items: center; border-bottom: 1px solid #e0e0e0; }
.toolbar select { padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
.toolbar .info { font-size: 12px; color: #888; }
.toolbar .risk-green { color: #2e7d32; }
.toolbar .risk-yellow { color: #e65100; }
.toolbar .risk-red { color: #c62828; }
.toolbar .risk-unknown { color: #888; }

.btn { padding: 7px 14px; border: none; border-radius: 4px; font-size: 13px; cursor: pointer; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn.primary { background: #1a73e8; color: #fff; }
.btn.primary:hover { background: #1557b0; }
.btn.danger { background: #e53935; color: #fff; }
.btn.danger:hover { background: #c62828; }

.main { display: flex; flex: 1; overflow: hidden; }
.main > :first-child { width: 200px; min-width: 200px; border-right: 1px solid #e0e0e0; }
.right { flex: 1; display: flex; flex-direction: column; border-left: 1px solid #e0e0e0; max-width: 420px; }
</style>
