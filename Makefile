# jav-idol-db —— 统一任务入口
# 用法：make <target>  （无 make 时看各 target 下方注释的等价命令）

PY ?= python3
SERVE_PORT ?= 8766

.PHONY: help build serve ingest ingest-all backfill-cover backfill-avatar audit test clean

help:  ## 显示可用目标
	@echo "可用目标:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

build:  ## 重新生成 data/index.json 与 site/assets/js/data.js
	$(PY) scripts/build_index.py

serve:  ## 本地预览站点（http://localhost:$(SERVE_PORT)/）
	cd site && $(PY) -m http.server $(SERVE_PORT)

ingest:  ## 抓取单个番号：make ingest CODE=IPX-005
	$(PY) scripts/scrape_codeav.py $(CODE)

ingest-all:  ## 批量重抓 data/works 全部作品（可续跑）
	$(PY) scripts/scrape_all.py

backfill-cover:  ## 封面热链回填（DMM 模板 + HTTP 校验）
	$(PY) tools/cover_backfill.py

backfill-avatar:  ## 女优头像补全（DMM 写真图床 + HTTP 校验）
	$(PY) tools/fill_avatars.py

test:  ## 运行数据完整性冒烟测试
	$(PY) -m unittest tests.test_data_integrity -v

audit:  ## 数据质量自检：字段覆盖率 / 女优作品数 / 缺关键字段清单
	$(PY) scripts/audit_fields.py

clean:  ## 删除 Python 缓存
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
