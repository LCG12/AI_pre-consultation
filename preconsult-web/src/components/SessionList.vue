<script setup>
import { ref, onMounted } from 'vue'
import { fetchSessions } from '../api.js'

const props = defineProps({ currentId: String })
const emit = defineEmits(['select'])

const sessions = ref([])
const loading = ref(false)

const labels = { created: '已创建', in_progress: '进行中', completed: '已完成', emergency: '紧急' }
const riskColors = { green: '#4caf50', yellow: '#ff9800', red: '#f44336', unknown: '#999' }

async function load() {
  loading.value = true
  try { sessions.value = await fetchSessions() } catch (e) { /* */ }
  loading.value = false
}

async function select(sid) {
  emit('select', sid)
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

onMounted(load)
defineExpose({ refresh: load })
</script>

<template>
  <div class="session-list">
    <div class="list-header">
      会话历史
      <button class="refresh-btn" @click="load" :disabled="loading">{{ loading ? '...' : '刷新' }}</button>
    </div>
    <div class="list-body" v-if="sessions.length">
      <div
        v-for="s in sessions" :key="s.session_code"
        :class="'item ' + (s.session_code === currentId ? 'active' : '')"
        @click="select(s.session_code)"
      >
        <div class="item-top">
          <span class="sid">{{ s.session_code.slice(-8) }}</span>
          <span class="status">{{ labels[s.status] || s.status }}</span>
        </div>
        <div class="item-bottom">
          <span class="time">{{ formatTime(s.created_at) }}</span>
          <span v-if="s.risk_level" class="risk" :style="{ color: riskColors[s.risk_level] || '#999' }">
            {{ { green: '绿', yellow: '黄', red: '红' }[s.risk_level] || s.risk_level }}
          </span>
        </div>
      </div>
    </div>
    <div v-else class="empty">暂无历史会话</div>
  </div>
</template>

<style scoped>
.session-list { display: flex; flex-direction: column; height: 100%; background: #fafafa; }
.list-header { padding: 10px 12px; font-size: 13px; font-weight: 600; color: #555; border-bottom: 1px solid #e0e0e0; display: flex; justify-content: space-between; align-items: center; }
.refresh-btn { padding: 3px 8px; border: 1px solid #ddd; border-radius: 4px; background: #fff; font-size: 11px; cursor: pointer; color: #666; }
.refresh-btn:hover { background: #f0f0f0; }

.list-body { flex: 1; overflow-y: auto; }
.item { padding: 10px 12px; border-bottom: 1px solid #eee; cursor: pointer; transition: background 0.15s; }
.item:hover { background: #e3f2fd; }
.item.active { background: #bbdefb; }
.item-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.sid { font-size: 12px; font-weight: 500; color: #333; font-family: monospace; }
.status { font-size: 10px; padding: 1px 6px; border-radius: 8px; background: #eee; color: #666; }
.time { font-size: 11px; color: #999; }
.item-bottom { display: flex; justify-content: space-between; align-items: center; }
.risk { font-size: 11px; font-weight: 600; }
.empty { padding: 40px 16px; text-align: center; color: #ccc; font-size: 13px; }
</style>
