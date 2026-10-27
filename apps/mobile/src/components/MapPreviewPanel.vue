<script setup lang="ts">
import { nextTick, onUnmounted, reactive, ref, watch } from 'vue';
import AppButton from './AppButton.vue';
import AccessibleButton from './AccessibleButton.vue';
import { labelTextControl } from '../platform/accessibility';
import { bindComposer } from '../platform/composer';
import { locationConsent, mapPreview, mapsStatus, searchPlaces, selectPlace, type SearchResult } from '../stores/maps';
import { readTaskDraft, type TaskDraft } from '../stores/task-drafts';
const props = defineProps<{ item: TaskDraft; disabled: boolean }>();
const emit = defineEmits<{ changed: [item: TaskDraft]; busy: [value: boolean] }>();
const open = ref(false); const busy = ref(false); const error = ref('');
const mode = ref<{ provider: string; configured: boolean } | null>(null);
const field = ref<'origin' | 'destination'>('origin');
const searchKind = ref<'poi' | 'address'>('poi');
const form = reactive({ city: '', query: '' });
const results = ref<SearchResult | null>(null);
const choosing = ref(false);
let cleanups: (() => void)[] = [];
function cleanup() { cleanups.forEach(fn => fn()); cleanups = []; }
onUnmounted(cleanup);
function controlId(name: string) { return `maps-${props.item.id}-${name}`; }
async function bind() {
  await nextTick(); cleanup();
  for (const [key, label] of [['city', '地点所在城市'], ['query', '具体地点或完整地址']] as const) {
    labelTextControl(controlId(key), label);
    cleanups.push(bindComposer(controlId(key), () => {}, () => {}, value => { form[key] = value; }, 'input'));
  }
}
watch([open, choosing, () => props.item.location_consent], bind);
watch(() => props.item.revision, () => { results.value = null; });
watch(field, () => { results.value = null; form.query = ''; });
watch(searchKind, () => { results.value = null; });
async function run(action: 'open' | 'consent' | 'withdraw' | 'search' | 'select' | 'preview' | 'reload', candidateId?: string) {
  if (busy.value || props.disabled) return;
  busy.value = true; error.value = ''; emit('busy', true);
  try {
    if (action === 'open') { open.value = true; mode.value = await mapsStatus(); await bind(); }
    else if (action === 'search') {
      if (form.city.trim().length < 2 || form.query.trim().length < 2) throw new Error('请填写城市和具体地点或完整地址');
      results.value = await searchPlaces(props.item, field.value, form.query.trim(), form.city.trim(), searchKind.value);
    } else {
      const item = candidateId && results.value
        ? await selectPlace(props.item, field.value, results.value.query_id, candidateId)
        : action === 'consent' || action === 'withdraw' ? await locationConsent(props.item, action === 'consent')
          : action === 'preview' ? await mapPreview(props.item) : await readTaskDraft(props.item.id);
      emit('changed', item); results.value = null; choosing.value = false;
      await nextTick(); await bind();
    }
  } catch (reason) { error.value = reason instanceof Error ? reason.message : '查询未完成，请重新核对'; }
  finally { busy.value = false; emit('busy', false); }
}
function displayTime(value?: string) { return value ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Hong_Kong', hour12: false }) : '未知'; }
</script>

<template>
  <view class="map-panel">
    <AppButton
      v-if="!open"
      secondary
      :loading="busy"
      :disabled="disabled"
      @click="run('open')"
    >
      核实地点、路线和天气
    </AppButton>
    <view
      v-if="open"
      class="map-content"
    >
      <text class="map-heading">
        地点与出行参考{{ mode?.provider === 'mock' ? ' · Mock / Synthetic' : '' }}
      </text>
      <text class="map-note">
        提醒尚未安排。查询只提供参考，不会自动通知；每次最多查询路线、天气各一次，相同条件短时间复用结果。
      </text>
      <text
        v-if="mode && !mode.configured"
        class="map-note"
      >
        地图天气未配置，请管理员在本机后端配置；这里不填写密钥。
      </text>
      <text
        v-if="mode?.provider === 'mock'"
        class="map-note"
      >
        当前使用固定合成地点、12公里/35分钟和模拟雨情，不能据此安排真实出行。
      </text>
      <template v-if="item.status !== 'deferred'">
        <text
          v-if="!item.location_consent"
          class="map-note"
        >
          同意后，仅在主动搜索/查询时将输入的城市、地点、所选坐标发给当前地图服务。不使用设备GPS，不从记忆猜家庭地址。
        </text>
        <AppButton
          v-if="!item.location_consent"
          :loading="busy"
          :disabled="disabled || !mode?.configured"
          @click="run('consent')"
        >
          同意本次行程的位置查询用途
        </AppButton>
        <view
          v-if="item.location_consent"
          class="map-content"
        >
          <text>出发地：{{ item.origin_place ? `${item.origin_place.name} · ${item.origin_place.address}` : '尚未选择具体地点' }}</text>
          <text>目的地：{{ item.destination_place ? `${item.destination_place.name} · ${item.destination_place.address}` : '尚未选择具体地点' }}</text>
          <template v-if="choosing || !item.origin_place || !item.destination_place">
            <view
              class="map-options"
              role="group"
              aria-label="选择要核实的地点"
            >
              <AccessibleButton
                :aria-pressed="field === 'origin'"
                :disabled="disabled || busy"
                @click="field = 'origin'"
              >
                搜索出发地
              </AccessibleButton>
              <AccessibleButton
                :aria-pressed="field === 'destination'"
                :disabled="disabled || busy"
                @click="field = 'destination'"
              >
                搜索目的地
              </AccessibleButton>
            </view>
            <view
              class="map-options"
              role="group"
              aria-label="地点查询方式"
            >
              <AccessibleButton
                :aria-pressed="searchKind === 'poi'"
                :disabled="disabled || busy"
                @click="searchKind = 'poi'"
              >
                地点名称
              </AccessibleButton>
              <AccessibleButton
                :aria-pressed="searchKind === 'address'"
                :disabled="disabled || busy"
                @click="searchKind = 'address'"
              >
                完整地址
              </AccessibleButton>
            </view>
            <label :for="controlId('city')">地点所在城市</label>
            <input
              :id="controlId('city')"
              v-model="form.city"
              :maxlength="40"
              :disabled="disabled || busy"
              placeholder="例如：北京市"
            >
            <label :for="controlId('query')">具体地点或完整地址</label>
            <input
              :id="controlId('query')"
              v-model="form.query"
              :maxlength="100"
              :disabled="disabled || busy"
              placeholder="请填写具体名称或含门牌号的地址"
            >
            <AppButton
              secondary
              :loading="busy"
              :disabled="disabled || !mode?.configured"
              @click="run('search')"
            >
              查询地点候选
            </AppButton>
            <view
              v-if="results"
              class="map-content"
            >
              <text>{{ results.is_synthetic ? 'Mock / Synthetic候选' : '高德候选' }} · {{ displayTime(results.fetched_at) }}（北京时间）</text>
              <text
                v-if="!results.items.length"
                class="map-note"
              >
                没有可用的具体位置，请补充地址；不会自动选择模糊地区。
              </text>
              <text
                v-if="results.items.length"
                class="map-note"
              >
                请选择并核对实际门牌、入口；不会默认选择第一项。
              </text>
              <AccessibleButton
                v-for="place in results.items"
                :key="place.id"
                class="map-candidate"
                :loading="busy"
                :disabled="disabled"
                @click="run('select', place.id)"
              >
                <text>选择：{{ place.name }}</text>
                <text>{{ place.district }} {{ place.address }} · {{ place.level }}</text>
              </AccessibleButton>
            </view>
          </template>
          <AccessibleButton
            v-if="item.origin_place && item.destination_place && !choosing"
            :disabled="disabled || busy"
            @click="choosing = true"
          >
            修改已选地点
          </AccessibleButton>
          <text
            v-if="item.missing_fields.length"
            class="map-note"
          >
            请先在信息卡补全：{{ item.missing_fields.join('、') }}
          </text>
          <AppButton
            :loading="busy"
            :disabled="disabled || !mode?.configured || !item.origin_place || !item.destination_place || item.missing_fields.length > 0"
            @click="run('preview')"
          >
            查询路线和天气
          </AppButton>
        </view>
      </template>
      <view
        v-if="item.map_snapshot"
        class="map-result"
      >
        <text>{{ item.map_snapshot.is_synthetic ? 'Mock / Synthetic出行参考' : '高德出行参考' }}</text>
        <text v-if="item.map_snapshot.route.duration_seconds">
          参考路程：{{ (item.map_snapshot.route.distance_m! / 1000).toFixed(1) }} 公里 · 约 {{ Math.ceil(item.map_snapshot.route.duration_seconds / 60) }} 分钟
        </text>
        <text v-else>
          路线不可用：{{ item.map_snapshot.route.message || '尚未查到可靠路线' }}
        </text>
        <text class="map-note">
          {{ item.map_snapshot.route.estimate_basis }}
        </text>
        <text class="map-note">
          获取：{{ displayTime(item.map_snapshot.route.fetched_at) }}；参考有效至：{{ displayTime(item.map_snapshot.expires_at) }}（北京时间）。超时请主动重新查询。
        </text>
        <text
          v-if="item.map_snapshot.expired"
          class="map-error"
        >
          出行参考已过期，请重新查询。
        </text>
        <template v-if="item.map_snapshot.weather.status === 'available'">
          <text>{{ item.map_snapshot.weather.date }} · {{ item.map_snapshot.weather.city }}：白天{{ item.map_snapshot.weather.dayweather }}，夜间{{ item.map_snapshot.weather.nightweather }}</text>
          <text>{{ item.map_snapshot.weather.umbrella_advice }}</text>
          <text class="map-note">
            预报发布：{{ displayTime(item.map_snapshot.weather.reporttime) }}（北京时间）。行政区/日期预报，不能确定某住址某分钟必然下雨。
          </text>
        </template>
        <text
          v-else
          class="map-note"
        >
          天气未知或超出预报范围，暂无可靠带伞建议。
        </text>
      </view>
      <AccessibleButton
        v-if="item.location_consent"
        :loading="busy"
        :disabled="disabled"
        @click="run('withdraw')"
      >
        撤回位置用途并清理查询结果
      </AccessibleButton>
      <text
        v-if="!item.location_consent"
        class="map-note"
      >
        坐标与查询结果不再使用；原始聊天和草案文字仍保留。
      </text>
      <view
        v-if="error"
        role="alert"
        class="map-error"
      >
        <text>{{ error }}</text>
        <AccessibleButton
          :loading="busy"
          :disabled="disabled"
          @click="run('reload')"
        >
          重新读取草案
        </AccessibleButton>
        <AccessibleButton
          v-if="!mode"
          :loading="busy"
          :disabled="disabled"
          @click="run('open')"
        >
          重新检查地图配置
        </AccessibleButton>
      </view>
      <AccessibleButton
        :disabled="disabled || busy"
        @click="open = false"
      >
        收起地点与出行参考
      </AccessibleButton>
    </view>
  </view>
</template>

<style scoped>
.map-panel,.map-content,.map-result { display: flex; flex-direction: column; gap: 10px; overflow-wrap: anywhere; }
.map-panel { border-top: 1px solid var(--color-line); padding-top: 12px; }
.map-heading { font-size: 18px; font-weight: 650; }.map-note { font-size: 15px; color: #52675f; }
.map-content input { min-height: 48px; width: 100%; padding: 10px; box-sizing: border-box; font-size: 17px; border: 1px solid #b7cbbf; border-radius: 10px; background: var(--color-bg); }
.map-options { display: flex; flex-wrap: wrap; gap: 8px; }.map-options button { min-height: 46px; padding: 8px 10px; border: 1px solid #9db9aa; border-radius: 10px; }
.map-options button[aria-pressed="true"] { background: var(--color-soft); font-weight: 600; }
.map-candidate { text-align: left; padding: 12px; border: 1px solid var(--color-line); border-radius: 12px; }
.map-result { padding: 12px; background: var(--color-bg); border-radius: 12px; }.map-error { color: var(--color-error); display: flex; flex-direction: column; gap: 8px; }
.map-content > button,.map-error button { min-height: 46px; }
</style>
