<script setup lang="ts">
import AppButton from '../../components/AppButton.vue';
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
interface Memory { id: string; value: string; time_expression: string | null; event_precision: string; extractor_provider: string | null; is_synthetic: boolean }
interface Source { source_excerpt: string; conversation_id: string; message: { id: string; content: string; created_at: string } }
const memories = ref<Memory[]>([]);
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
async function runSearch() { if (loading.value) return; appliedQuery.value = query.value.trim(); await load(false); }
async function clearSearch() { if (loading.value) return; query.value = ''; appliedQuery.value = ''; await load(false); }
async function load(more = false) {
  if (loading.value) return;
  loading.value = true; error.value = '';
  try {
    const page = await request<{ items: Memory[]; next_cursor: string | null }>(appliedQuery.value ? `/memories/search?q=${encodeURIComponent(appliedQuery.value)}` : `/memories${more && cursor.value ? `?before_id=${cursor.value}` : ''}`);
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
          这里只显示从你的聊天提取的候选记忆，可以核对来源。
        </text><text class="preview-label">
          候选仍待确认 · 不补写未发生的细节
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
          <text class="memory-label">
            {{ memory.extractor_provider === 'mock' ? 'Mock 抽取候选 · 待确认' : '候选记忆 · 待确认' }}{{ memory.is_synthetic ? ' · Synthetic' : '' }}
          </text>
          <text class="memory-value">
            {{ memory.value }}
          </text>
          <text class="memory-label">
            时间：{{ memory.time_expression || '未明确' }}；精度：{{ memory.event_precision === 'month' ? '月份' : memory.event_precision === 'year' ? '年份' : memory.event_precision === 'day' ? '日期' : '未明确' }}
          </text>
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
.memory-card { margin-top: 18px; display: flex; flex-direction: column; gap: 12px; }
.memory-label { display: block; font-size: 15px; color: var(--color-muted); line-height: 1.6; }
.memory-value, .source-card { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.8; }
.source-card { border-top: 1px solid var(--color-line); padding-top: 12px; }
.memory-search { display: flex; align-items: center; gap: 8px; margin: 16px 0; }
.search-input { flex: 1; min-width: 0; min-height: 52px; padding: 8px 12px; border: 1px solid var(--color-line); border-radius: 14px; font-size: 18px; color: var(--color-text); background: white; }
</style>
