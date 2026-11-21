ROLES = ('admin', 'operator', 'viewer')
RUN_STATES = ('queued', 'running', 'completed', 'failed')
# 复核库同步状态：empty 未复制 / copying 初次复制 / syncing 待接增量 / ready 可核对 / blocked 断档暂停
SYNC_STATES = ('empty', 'copying', 'syncing', 'ready', 'blocked')
SYNC_BLOCKED_REASONS = ('gap', 'incomplete', 'apply_error')
