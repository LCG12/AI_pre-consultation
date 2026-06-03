<script setup>
import { ref, watch, nextTick } from 'vue'
import { sendMessage, getResult, getMessages } from '../api.js'

const props = defineProps({ sessionId: String, state: Object, completed: Boolean })
const emit = defineEmits(['stateUpdate'])

const messages = ref([])
const input = ref('')
const quickReplies = ref([])
const chatEl = ref(null)

watch(() => props.sessionId, (sid) => {
  if (sid) {
    messages.value = [{ role: 'assistant', message_text: '请问您哪里不舒服？' }]
    quickReplies.value = []
  } else {
    messages.value = []
    quickReplies.value = []
  }
})

async function loadState() {
  if (!props.sessionId) return
  try {
    const s = await getResult(props.sessionId)
    emit('stateUpdate', s)
  } catch (e) { /* */ }
}

async function send(text) {
  if (!text.trim() || !props.sessionId || props.completed) return
  messages.value.push({ role: 'patient', message_text: text.trim() })
  try {
    const resp = await sendMessage(props.sessionId, text.trim())
    messages.value.push({ role: 'assistant', message_text: resp.reply })
    quickReplies.value = resp.quick_replies || []
    await loadState()
    await nextTick()
    scrollBottom()
  } catch (e) { alert('发送失败: ' + e.message) }
}

function onKey(e) {
  if (e.key === 'Enter') { send(input.value); input.value = '' }
}

function scrollBottom() {
  if (chatEl.value) chatEl.value.scrollTop = chatEl.value.scrollHeight
}
</script>

<template>
  <div class="chat-panel">
    <div class="chat-header">
      对话记录
      <span v-if="state.status==='completed'" class="tag done">已完成</span>
      <span v-else-if="state.status==='emergency'" class="tag emergency">紧急</span>
      <span v-else-if="sessionId" class="tag active">进行中</span>
    </div>

    <div class="messages" ref="chatEl">
      <div v-if="!messages.length" class="empty">
        <div class="empty-icon">💬</div>
        <p>点击“新建会话”开始预问诊</p>
      </div>
      <div v-for="(msg, i) in messages" :key="i" :class="'msg ' + msg.role">
        <div class="avatar">{{ msg.role === 'assistant' ? '医' : '患' }}</div>
        <div class="bubble">{{ msg.message_text }}</div>
      </div>
    </div>

    <div class="quick-row" v-if="quickReplies.length && !completed">
      <button v-for="qr in quickReplies" :key="qr" class="qr-btn" @click="send(qr); input=''">{{ qr }}</button>
    </div>

    <div class="input-row">
      <input v-model="input" @keyup.enter="onKey" placeholder="输入患者消息..."
        :disabled="!sessionId || completed" />
      <button class="btn primary" @click="send(input); input=''" :disabled="!sessionId || !input.trim() || completed">
        发送
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-panel { flex: 2; display: flex; flex-direction: column; background: #fff; }
.chat-header { padding: 10px 16px; border-bottom: 1px solid #eee; font-size: 13px; font-weight: 600; color: #555; display: flex; align-items: center; gap: 8px; }
.tag { font-size: 11px; padding: 2px 8px; border-radius: 10px; }
.tag.done { background: #e8f5e9; color: #2e7d32; }
.tag.emergency { background: #ffebee; color: #c62828; }
.tag.active { background: #e3f2fd; color: #1565c0; }

.messages { flex: 1; overflow-y: auto; padding: 16px; }
.empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #ccc; }
.empty-icon { font-size: 48px; }
.empty p { font-size: 14px; margin-top: 8px; }

.msg { display: flex; gap: 10px; margin-bottom: 16px; }
.msg.patient { flex-direction: row-reverse; }
.avatar { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 13px; flex-shrink: 0; }
.msg.assistant .avatar { background: #e3f2fd; color: #1a73e8; }
.msg.patient .avatar { background: #fce4ec; color: #e91e63; }
.bubble { max-width: 75%; padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.5; }
.msg.assistant .bubble { background: #f5f5f5; border-bottom-left-radius: 4px; }
.msg.patient .bubble { background: #1a73e8; color: #fff; border-bottom-right-radius: 4px; }

.quick-row { display: flex; gap: 8px; flex-wrap: wrap; padding: 0 16px 8px; }
.qr-btn { padding: 6px 14px; border: 1px solid #1a73e8; border-radius: 16px; background: #fff; color: #1a73e8; font-size: 12px; cursor: pointer; }
.qr-btn:hover { background: #1a73e8; color: #fff; }

.input-row { padding: 10px 16px; border-top: 1px solid #eee; display: flex; gap: 8px; }
.input-row input { flex: 1; padding: 10px 14px; border: 1px solid #ddd; border-radius: 20px; font-size: 14px; outline: none; }
.input-row input:focus { border-color: #1a73e8; }
</style>
