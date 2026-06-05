<script setup>
import { computed } from 'vue'

const props = defineProps({ state: Object, departments: Array })

const LABELS = {
  'location': '位置', 'pain_type': '性质', 'severity': '程度',
  'duration_hours': '持续(时)', 'radiation': '放射', 'onset': '起病',
  'eating_relationship': '进食关系', 'bowel_movement': '排便',
  'sore_throat': '咽痛', 'fatigue': '乏力', 'headache': '头痛',
  'diarrhea': '腹泻', 'rash': '皮疹', 'nausea_vomiting': '恶心呕吐',
  'constipation': '便秘', 'fever': '伴发热',
  'shortness_of_breath': '呼吸困难', 'chest_pain': '胸痛',
  'hemoptysis': '咳血', 'confusion': '意识模糊', 'seizure': '抽搐',
  'cyanosis': '发绀', 'peritoneal_signs': '腹膜刺激征',
  'hematemesis': '呕血', 'melena': '黑便', 'syncope': '晕厥',
  'thunderclap_onset': '雷击样发作', 'neuro_symptoms': '神经症状',
  'fever_stiff_neck': '发热颈强直', 'trauma_anticoag': '外伤/抗凝',
  'new_onset_over_50': '50岁后新发', 'worsening_pattern': '进行性加重',
  'pregnancy_related': '妊娠相关', 'eye_symptoms': '眼部症状',
}

const VALUE_MAP = {
  'dull':'钝痛','colicky':'绞痛','stabbing':'刺痛','distension':'胀痛','burning':'烧灼痛',
  'right_lower':'右下腹','left_lower':'左下腹','right_upper':'右上腹','left_upper':'左上腹',
  'upper_abdomen':'上腹部','lower_abdomen':'下腹部','periumbilical':'脐周','diffuse':'全腹',
  'mild':'轻度','moderate':'中度','severe':'重度','sudden':'突发','gradual':'逐渐',
  'dry':'干咳','productive':'有痰','none':'无',
  'before_meal':'餐前加重','after_meal':'餐后加重','unrelated':'无关',
  'female':'女','male':'男',
}

function isUncertain(path) {
  return !!path && (props.state?.dialogue?.uncertain_slots || []).includes(path)
}

function fmtVal(v, path) {
  if (isUncertain(path)) return { text: '不确定', cls: 'uncertain' }
  if (v === null || v === undefined) return { text: '未采集', cls: 'null' }
  if (typeof v === 'boolean') return { text: v ? '是' : '否', cls: v ? 'true' : 'false' }
  const s = String(v)
  return { text: VALUE_MAP[s] || s, cls: 'text' }
}

function fieldRows(prefix, keys) {
  const src = props.state?.slots?.[prefix]
  if (!src) return []
  const hasAny = keys.some(k => src[k] !== null && src[k] !== undefined || isUncertain(`slots.${prefix}.${k}`))
  if (!hasAny) return []
  return keys.map(k => {
    const path = `slots.${prefix}.${k}`
    return { key: k, path, label: LABELS[k] || k, ...fmtVal(src[k], path) }
  })
}

const hasAbdominal = computed(() => fieldRows('abdominal_pain', ['location','pain_type','severity','duration_hours','radiation','onset','eating_relationship','bowel_movement']).length > 0)
const hasFever = computed(() => fieldRows('fever', ['duration_days','max_temperature_c']).length > 0)
const hasCough = computed(() => fieldRows('cough', ['has_cough','cough_type','sputum']).length > 0)
const hasAssociated = computed(() => fieldRows('associated_symptoms', ['nausea_vomiting','diarrhea','constipation','fever','sore_throat','fatigue','headache','rash']).length > 0)
const hasHeadache = computed(() => fieldRows('headache', ['onset_speed','location','pain_type','severity','duration_hours','frequency']).length > 0)
const hasHeadacheRF = computed(() => {
  const src = props.state?.slots?.headache?.red_flags
  if (!src) return false
  return Object.entries(src).some(([k, v]) => v !== null && v !== undefined || isUncertain(`slots.headache.red_flags.${k}`))
})
const hasRedFlags = computed(() => fieldRows('red_flags', ['peritoneal_signs','hematemesis','melena','syncope','shortness_of_breath','chest_pain','hemoptysis','confusion','seizure','cyanosis']).length > 0)
</script>

<template>
  <div class="state-panel">
    <div class="panel-title">State 字段状态</div>
    <div class="content" v-if="state.session_id">
      <div class="section">
        <div class="s-title">基本信息</div>
        <div class="row"><span class="r-label">路径</span><span class="r-val text">{{ state.path_id }}</span></div>
        <div class="row"><span class="r-label">轮次</span><span class="r-val number">{{ state.dialogue?.turn_count || 0 }}</span></div>
        <div class="row"><span class="r-label">缺失</span><span class="r-val number">{{ (state.dialogue?.missing_required_slots || []).length }}</span></div>
        <div class="row"><span class="r-label">不确定</span><span class="r-val uncertain">{{ (state.dialogue?.uncertain_slots || []).length }}</span></div>
        <div class="row"><span class="r-label">风险</span><span class="r-val text">{{ state.risk?.current_level }}</span></div>
        <div class="row" v-if="departments.length"><span class="r-label">科室</span><span class="r-val text">{{ departments.join('、') }}</span></div>
      </div>

      <div class="section" v-if="state.patient_basic_info">
        <div class="s-title">患者</div>
        <div class="row" v-for="(v,k) in state.patient_basic_info" :key="k">
          <span class="r-label">{{ k }}</span>
          <span :class="'r-val ' + fmtVal(v, `patient_basic_info.${k}`).cls">{{ fmtVal(v, `patient_basic_info.${k}`).text }}</span>
        </div>
      </div>

      <div class="section" v-if="state.chief_complaint?.main_symptoms?.length">
        <div class="s-title">主诉</div>
        <div class="row"><span class="r-label">症状</span><span class="r-val text">{{ state.chief_complaint.main_symptoms.join(', ') }}</span></div>
        <div class="row"><span class="r-label">持续天数</span><span :class="'r-val ' + fmtVal(state.chief_complaint.duration_days, 'chief_complaint.duration_days').cls">{{ fmtVal(state.chief_complaint.duration_days, 'chief_complaint.duration_days').text }}</span></div>
      </div>

      <div class="section" v-if="hasFever">
        <div class="s-title">发热</div>
        <div class="row" v-for="r in fieldRows('fever', ['duration_days','max_temperature_c'])" :key="r.key">
          <span class="r-label">{{ r.label }}</span><span :class="'r-val ' + r.cls">{{ r.text }}</span>
        </div>
      </div>

      <div class="section" v-if="hasCough">
        <div class="s-title">咳嗽</div>
        <div class="row" v-for="r in fieldRows('cough', ['has_cough','cough_type','sputum'])" :key="r.key">
          <span class="r-label">{{ r.label }}</span><span :class="'r-val ' + r.cls">{{ r.text }}</span>
        </div>
      </div>

      <div class="section" v-if="hasAbdominal">
        <div class="s-title">腹痛</div>
        <div class="row" v-for="r in fieldRows('abdominal_pain', ['location','pain_type','severity','duration_hours','radiation','onset','eating_relationship','bowel_movement'])" :key="r.key">
          <span class="r-label">{{ r.label }}</span><span :class="'r-val ' + r.cls">{{ r.text }}</span>
        </div>
      </div>

      <div class="section" v-if="hasHeadache">
        <div class="s-title">头痛</div>
        <div class="row" v-for="r in fieldRows('headache', ['onset_speed','location','pain_type','severity','duration_hours','frequency'])" :key="r.key">
          <span class="r-label">{{ r.label }}</span><span :class="'r-val ' + r.cls">{{ r.text }}</span>
        </div>
      </div>

      <div class="section" v-if="hasHeadacheRF">
        <div class="s-title">头痛红旗</div>
        <div class="row" v-for="(v,k) in state.slots?.headache?.red_flags || {}" :key="k">
          <span class="r-label">{{ LABELS[k] || k }}</span>
          <span :class="'r-val ' + fmtVal(v, `slots.headache.red_flags.${k}`).cls">{{ fmtVal(v, `slots.headache.red_flags.${k}`).text }}</span>
        </div>
      </div>

      <div class="section" v-if="hasAssociated">
        <div class="s-title">伴随症状</div>
        <div class="row" v-for="r in fieldRows('associated_symptoms', ['nausea_vomiting','diarrhea','constipation','fever','sore_throat','fatigue','headache','rash'])" :key="r.key">
          <span class="r-label">{{ r.label }}</span><span :class="'r-val ' + r.cls">{{ r.text }}</span>
        </div>
      </div>

      <div class="section" v-if="hasRedFlags">
        <div class="s-title">红旗信号</div>
        <div class="row" v-for="r in fieldRows('red_flags', ['peritoneal_signs','hematemesis','melena','syncope','shortness_of_breath','chest_pain','hemoptysis','confusion','seizure','cyanosis'])" :key="r.key">
          <span class="r-label">{{ r.label }}</span><span :class="'r-val ' + r.cls">{{ r.text }}</span>
        </div>
      </div>

      <div class="section">
        <div class="s-title">过敏/用药</div>
        <div class="row"><span class="r-label">过敏</span><span :class="'r-val ' + fmtVal(state.slots?.allergy_history?.has_allergy, 'slots.allergy_history.has_allergy').cls">{{ fmtVal(state.slots?.allergy_history?.has_allergy, 'slots.allergy_history.has_allergy').text }}</span></div>
        <div class="row"><span class="r-label">过敏详情</span><span :class="'r-val ' + fmtVal(state.slots?.allergy_history?.detail, 'slots.allergy_history.detail').cls">{{ fmtVal(state.slots?.allergy_history?.detail, 'slots.allergy_history.detail').text }}</span></div>
        <div class="row"><span class="r-label">用药</span><span :class="'r-val ' + fmtVal(state.slots?.medication_history?.has_used_medicine, 'slots.medication_history.has_used_medicine').cls">{{ fmtVal(state.slots?.medication_history?.has_used_medicine, 'slots.medication_history.has_used_medicine').text }}</span></div>
        <div class="row"><span class="r-label">用药详情</span><span :class="'r-val ' + fmtVal(state.slots?.medication_history?.detail, 'slots.medication_history.detail').cls">{{ fmtVal(state.slots?.medication_history?.detail, 'slots.medication_history.detail').text }}</span></div>
      </div>
    </div>
    <div v-else class="empty">创建会话后展示 State</div>
  </div>
</template>

<style scoped>
.state-panel { display: flex; flex-direction: column; background: #fafafa; flex: 1; overflow: hidden; }
.panel-title { padding: 10px 16px; border-bottom: 1px solid #e0e0e0; font-size: 13px; font-weight: 600; color: #555; }
.content { flex: 1; overflow-y: auto; padding: 12px; }
.empty { padding: 40px 16px; text-align: center; color: #ccc; font-size: 14px; }

.section { margin-bottom: 14px; }
.s-title { font-size: 11px; font-weight: 600; color: #999; text-transform: uppercase; margin-bottom: 4px; padding-bottom: 2px; border-bottom: 1px solid #eee; }
.row { display: flex; justify-content: space-between; padding: 3px 0; font-size: 12px; }
.r-label { color: #666; }
.r-val { font-weight: 500; max-width: 60%; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.r-val.null { color: #ccc; font-style: italic; }
.r-val.true { color: #d32f2f; }
.r-val.false { color: #4caf50; }
.r-val.text { color: #1a73e8; }
.r-val.number { color: #ff6f00; }
.r-val.uncertain { color: #8a6d00; }
</style>
