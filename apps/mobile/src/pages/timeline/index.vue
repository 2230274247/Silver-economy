<script setup lang="ts">
import AppButton from '../../components/AppButton.vue';
import MemoryControls from '../../components/MemoryControls.vue';
import { type Memory, memoryStatus } from '../../stores/memory';
import { invalidateMemoryReferences } from '../../stores/chat';
import AppHeader from '../../components/AppHeader.vue';
import BottomTabs from '../../components/BottomTabs.vue';
import EmptyState from '../../components/EmptyState.vue';
import MobileShell from '../../components/MobileShell.vue';
import { onLoad } from '@dcloudio/uni-app';
import { ref, nextTick, onMounted, onUnmounted } from 'vue';
import { request } from '../../platform/network';
import { requestId } from '../../platform/ids';
import { bindComposer } from '../../platform/composer';
import { labelTextControl } from '../../platform/accessibility';
type TimelineMemory = Memory & { event_label?: string; source_count?: number; recorded_at?: string };
interface Source { source_excerpt: string; conversation_id: string; message: { id: string; content: string; created_at: string } }
const memories = ref<TimelineMemory[]>([]);
const viewMode = ref<'library' | 'timeline'>('library');
const loading = ref(false);
const error = ref('');
const cursor = ref<string | null>(null);
const sources = ref<Record<string, Source[]>>({});
const sourceBusy = ref('');
const sourceCursor = ref<Record<string, string | null>>({});
const searchId = `memory-search-${requestId()}`;
const query = ref('');
const appliedQuery = ref('');
let removeSearch = () => {};
onMounted(async () => { await nextTick(); labelTextControl(searchId, '搜索我的记忆'); removeSearch = bindComposer(searchId, runSearch, () => {}, value => { query.value = value; }, 'input'); });
onUnmounted(() => removeSearch());
function updateQuery(event: Event) {
  // #ifndef H5
  query.value = (event as unknown as { detail: { value: string } }).detail.value;
  // #endif
  void event;
}
function confirmSearch(event: Event) { query.value = (event as unknown as { detail: { value: string } }).detail.value; void runSearch(); }
async function runSearch() { if (loading.value) return; viewMode.value = 'library'; appliedQuery.value = query.value.trim(); await load(false); }
async function clearSearch() { if (loading.value) return; viewMode.value = 'library'; query.value = ''; appliedQuery.value = ''; await load(false); }
async function load(more = false) {
  if (loading.value) return;
  loading.value = true; error.value = '';
  try {
    const page = await request<{ items: TimelineMemory[]; next_cursor: string | null }>(appliedQuery.value ? `/memories/search?q=${encodeURIComponent(appliedQuery.value)}` : `/memories${viewMode.value === 'timeline' ? '/timeline' : ''}${more && cursor.value ? `?before_id=${cursor.value}` : ''}`);
    memories.value = more ? [...memories.value, ...page.items] : page.items; cursor.value = page.next_cursor;
  } catch (reason) { error.value = reason instanceof Error ? reason.message : '记忆读取失败'; }
  finally { loading.value = false; }
}
async function viewSources(id: string, more = false) {
  if (sourceBusy.value) return;
  sourceBusy.value = id; error.value = '';
  try {
    const page = await request<{ items: Source[]; next_cursor: string | null }>(`/memories/${id}/sources${more && sourceCursor.value[id] ? `?before_id=${sourceCursor.value[id]}` : ''}`);
    sources.value[id] = more ? [...sources.value[id], ...page.items] : page.items; sourceCursor.value[id] = page.next_cursor;
  }
  catch { error.value = '来源读取失败，请再次点击查看来源重试。'; }
  finally { sourceBusy.value = ''; }
}
async function chooseView(mode: 'library' | 'timeline') {
  if (loading.value || viewMode.value === mode) return;
  viewMode.value = mode; query.value = ''; appliedQuery.value = ''; memories.value = []; cursor.value = null; await load();
}
function updatedMemory(item: Memory) {
  memories.value = memories.value.map(old => old.id === item.id ? { ...old, ...item } : old);
  invalidateMemoryReferences(item.id); error.value = '';
  if (viewMode.value === 'timeline') void load();
}
function deletedMemory(id: string) {
  memories.value = memories.value.filter(item => item.id !== id);
  delete sources.value[id]; delete sourceCursor.value[id];
  invalidateMemoryReferences(id, true); error.value = '';
  void load();
}
function openSource(source: Source) { uni.navigateTo({ url: `/pages/index/index?id=${source.conversation_id}` }); }
onLoad(() => { void load(); });
function openChat() { uni.redirectTo({ url: '/pages/index/index' }); }
</script>

<template>
  <MobileShell>
    <template #header>
      <AppHeader title="我的回忆" />
    </template>
    <scroll-view
      scroll-y
      class="content-scroll"
    >
      <view class="page-content">
        <text class="page-title">
          值得记住的，都在这里。
        </text><text class="page-description">
          可以核对来源、确认和纠错。删除长期记忆不会删除原始聊天。
        </text><text class="preview-label">
          候选待确认 · 历史与当前状态分开保存
        </text>
        <view
          class="view-options"
          role="group"
          aria-label="回忆查看方式"
        >
          <AppButton
            secondary
            :disabled="loading"
            :aria-pressed="viewMode === 'library'"
            @click="chooseView('library')"
          >
            记忆列表
          </AppButton>
          <AppButton
            secondary
            :disabled="loading"
            :aria-pressed="viewMode === 'timeline'"
            @click="chooseView('timeline')"
          >
            按时间查看
          </AppButton>
        </view>
        <text
          v-if="viewMode === 'timeline'"
          class="memory-label"
        >
          按事情发生的时间范围排列；未明确发生时间的按记录时间排列。年份、月份不代表已确定具体哪一天。
        </text>
        <text
          v-if="loading"
          role="status"
        >
          正在读取记忆…
        </text>
        <view class="memory-search">
          <input
            :id="searchId"
            :value="query"
            class="search-input"
            placeholder="找一找，比如苏州、工作"
            :maxlength="200"
            :ignore-composition-event="false"
            confirm-type="search"
            @input="updateQuery"
            @confirm="confirmSearch"
          >
          <AppButton
            style="width:84px;flex-shrink:0"
            secondary
            :loading="loading"
            @click="runSearch"
          >
            搜索
          </AppButton>
        </view>
        <view
          v-if="appliedQuery"
          class="memory-label"
        >
          搜索“{{ appliedQuery }}”，最多显示30条相关结果。<AppButton
            secondary
            :disabled="loading"
            @click="clearSearch"
          >
            清除搜索
          </AppButton>
        </view>
        <view
          v-if="error"
          role="alert"
        >
          <text>{{ error }}</text><AppButton
            secondary
            :loading="loading"
            @click="load(false)"
          >
            重新读取
          </AppButton>
        </view>
        <view
          v-for="memory in memories"
          :id="`memory-${memory.id}`"
          :key="memory.id"
          class="surface-card memory-card"
        >
          <text
            v-if="viewMode === 'timeline'"
            class="event-label"
          >
            {{ memory.event_label }}
          </text>
          <text
            v-if="viewMode === 'timeline'"
            class="memory-label"
          >
            {{ memory.source_count }} 段原文依据 · 记录于 {{ new Date(memory.recorded_at || '').toLocaleString('zh-CN') }}
          </text>
          <text class="memory-label">
            {{ memoryStatus(memory) }}
          </text>
          <text class="memory-value">
            {{ memory.value }}
          </text>
          <text class="memory-label">
            时间：{{ memory.time_expression || '未明确' }}；精度：{{ memory.event_precision === 'month' ? '月份' : memory.event_precision === 'year' ? '年份' : memory.event_precision === 'day' ? '日期' : '未明确' }}
          </text>
          <MemoryControls
            :memory="memory"
            @updated="updatedMemory"
            @deleted="deletedMemory"
          />
          <AppButton
            secondary
            :loading="sourceBusy === memory.id"
            :disabled="!!sourceBusy && sourceBusy !== memory.id"
            @click="viewSources(memory.id)"
          >
            查看来源
          </AppButton>
          <view
            v-for="source in sources[memory.id] || []"
            :key="source.message.id"
            class="source-card"
          >
            <text>原文：{{ source.source_excerpt }}</text><text class="memory-label">
              记录于 {{ new Date(source.message.created_at).toLocaleString('zh-CN') }}
            </text>
            <AppButton
              secondary
              @click="openSource(source)"
            >
              返回原会话
            </AppButton>
          </view>
          <AppButton
            v-if="sourceCursor[memory.id]"
            secondary
            :loading="sourceBusy === memory.id"
            :disabled="!!sourceBusy && sourceBusy !== memory.id"
            @click="viewSources(memory.id, true)"
          >
            查看更多来源
          </AppButton>
        </view>
        <AppButton
          v-if="cursor"
          secondary
          :loading="loading"
          @click="load(true)"
        >
          查看更多记忆
        </AppButton>
      </view>
      <EmptyState
        v-if="!loading && !memories.length && !error"
        icon="notebook-pen"
        :title="appliedQuery ? '没有找到相关记忆' : '故事，从一段聊天开始'"
        :description="appliedQuery ? '可以换个说法，系统不会编造不存在的经历。' : '先在个人设置开启长期记忆，再聊聊你明确经历过的事情。'"
      >
        <AppButton
          secondary
          @click="openChat"
        >
          去聊聊天
        </AppButton>
      </EmptyState>
    </scroll-view>
    <template #footer>
      <BottomTabs active="timeline" />
    </template>
  </MobileShell>
</template>

<style scoped>
.content-scroll { height: 0; flex: 1; }
.view-options { display: flex; gap: 10px; margin: 16px 0; }
.event-label { display: block; color: var(--color-primary-dark); font-size: 20px; font-weight: 600; }
.memory-card { margin-top: 18px; display: flex; flex-direction: column; gap: 12px; }
.memory-label { display: block; font-size: 15px; color: var(--color-muted); line-height: 1.6; }
.memory-value, .source-card { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.8; }
.source-card { border-top: 1px solid var(--color-line); padding-top: 12px; }
.memory-search { display: flex; align-items: center; gap: 8px; margin: 16px 0; }
.search-input { flex: 1; min-width: 0; min-height: 52px; padding: 8px 12px; border: 1px solid var(--color-line); border-radius: 14px; font-size: 18px; color: var(--color-text); background: white; }
</style>
