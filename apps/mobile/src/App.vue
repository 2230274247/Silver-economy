<script setup lang="ts">
import { onLaunch } from '@dcloudio/uni-app';
import { restoreSession } from './stores/session';
onLaunch(() => { void restoreSession(); });
</script>

<style>
@import './styles/tokens.css';
@import './styles/base.css';
</style>
