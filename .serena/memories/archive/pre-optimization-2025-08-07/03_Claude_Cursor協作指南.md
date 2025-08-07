# Claude_Cursor協作指南 - 實戰協作流程

## 🤝 核心協作流程設計

### 實戰協作原則
**Claude Code說：** 「我規專案系統流程步驟todo step by step方案」  
**Serena記住：** 「存入專案架構總覽 + Claude_Code完成工作記錄」  
**Cursor讀取：** 「從Claude_Cursor協作指南了解流程，從Cursor完成工作記錄追蹤進度」

## 📝 四種記憶文件實戰分類

基於實際Cursor IDE操作介面，Serena MCP提供四種標準化記憶文件分類：

### 1. 🤝 Claude_Cursor協作指南 - 協作開發指南
**用途：** 定義AI間協作流程和開發規範
- 協作模式說明和工作流程
- Claude Code與Cursor的分工界限（在過程中Mixed不同層級的claude code agents 和studio ai agents的應用）
- 項目狀態追蹤機制
- 溝通標準和格式規範
- 跨專案通用的協作模式

### 2. 📝 Cursor完成工作記錄 - 工作完成記錄
**用途：** 追蹤具體實作進度和完成狀態
- 組件開發完成清單
- 功能實現進度記錄
- 錯誤修復完成狀態
- 測試驗證結果記錄
- 實際開發過程中的問題和解決方案

### 3. 🏗️ 專案架構總覽 - 項目架構概覽
**用途：** 記錄整體技術方案和系統設計
- 技術棧選型和架構設計
- 系統結構和模組分工
- 資料流和狀態管理方案
- 建置系統和部署策略
- 性能優化和安全考量

### 4. 💻 Claude_Code完成工作記錄 - 代碼完成記錄
**用途：** 記錄代碼規劃和設計完成狀態
- 技術方案設計完成記錄
- 架構規劃和標準制定
- 組件模板和樣式標準
- TypeScript 類型定義標準
- 最佳實踐和開發指引

## 🔄 AI代理協作工作流程

### Phase 1: 項目啟動和規劃
```
Claude Code (規劃主導) → Serena Memory (記錄存儲) → Cursor (實作準備)
```
1. **Claude Code**: 使用38個專業代理分析需求和設計架構
   - `rapid-prototyper`: 快速原型概念設計
   - `backend-architect`: 系統架構規劃
   - `frontend-developer`: 前端技術棧選擇
   - `studio-coach`: 協調多代理任務

2. **Serena Memory**: 記錄規劃結果
   - 更新「專案架構總覽」
   - 更新「Claude_Code完成工作記錄」

3. **Cursor準備**: 讀取協作指南，了解技術棧和實作要求

### Phase 2: 開發實作階段
```
Cursor (實作主導) → Claude Code (顧問支持) → Serena Memory (狀態追蹤)
```
1. **Cursor主導開發**: 
   - 根據架構總覽開始編碼
   - 實作具體功能組件
   - 處理實際開發問題

2. **Claude Code支持**: 
   - `test-writer-fixer`: 自動化測試支持
   - `performance-benchmarker`: 效能優化建議
   - `devops-automator`: 部署和CI/CD支持

3. **Serena Memory追蹤**: 
   - 更新「Cursor完成工作記錄」
   - 記錄遇到的問題和解決方案

### Phase 3: 品質保證和優化
```
Claude Code (品質檢查) ↔ Cursor (修復實作) ↔ Serena Memory (結果記錄)
```
1. **Claude Code質量檢查**: 
   - `code-reviewer`: 代碼審查
   - `api-tester`: API測試驗證
   - `workflow-optimizer`: 流程優化建議

2. **Cursor修復和優化**: 
   - 根據檢查結果修復問題
   - 實作性能優化建議
   - 完善測試覆蓋率

3. **Serena Memory最終記錄**: 
   - 完整更新四種記憶文件
   - 記錄最終交付狀態

## 🎯 分工界限和責任劃分

### Claude Code責任範圍
- ✅ **系統設計和架構規劃** - 利用38個專業代理
- ✅ **技術方案制定** - `backend-architect`, `frontend-developer`
- ✅ **品質檢查和優化建議** - `test-writer-fixer`, `performance-benchmarker`
- ✅ **複雜邏輯設計** - `ai-engineer`, `rapid-prototyper`
- ❌ **具體代碼實作** - 由Cursor負責
- ❌ **IDE操作和調試** - 由Cursor負責

### Cursor責任範圍
- ✅ **具體代碼實作** - 根據Claude Code提供的設計
- ✅ **IDE操作和項目管理** - 文件創建、依賴管理
- ✅ **實際運行和調試** - 解決運行時問題
- ✅ **用戶界面實作** - 根據設計實現UI/UX
- ❌ **系統架構設計** - 由Claude Code負責
- ❌ **複雜算法設計** - 由Claude Code AI代理負責

### Serena Memory責任範圍
- ✅ **狀態持久化** - 保存四種記憶文件
- ✅ **協作協調** - 提供跨對話的連續性
- ✅ **進度追蹤** - 記錄完成狀態和待辦事項
- ✅ **知識積累** - 跨專案的經驗復用

## 🚀 四種記憶文件的革命性價值

### 標準化可複用
- 四種分類可應用於任何專案
- 不再是專案特定的臨時方案
- 形成跨專案的標準化AI協作工作流程

### 職責清晰分工
- 每種記憶文件有明確的用途和責任
- Claude Code → 專案架構總覽 + Claude_Code完成工作記錄
- Cursor → Claude_Cursor協作指南 + Cursor完成工作記錄

### 避免遺忘問題
- 解決了「自己會忘記，AI也會忘記」的核心痛點
- 結構化記憶讓協作持續性成為可能
- 跨對話的真正同步協作

### 真正持續協作
- 從專案結束即中斷，變成跨專案通用
- AI協作變成標準化流程，而非臨時搭建
- 可以無縫應用到任何新專案

## 🔄 溝通標準和格式規範

### 狀態報告格式
```markdown
## 📋 當前狀態報告
- **Phase**: [Phase 1/2/3]
- **主導方**: [Claude Code/Cursor]
- **完成進度**: [具體百分比]
- **當前任務**: [具體描述]
- **下一步計劃**: [具體行動]
- **需要協作**: [具體需求]
```

### 問題升級機制
1. **Level 1**: Cursor可以獨立解決的實作問題
2. **Level 2**: 需要Claude Code特定代理支持的問題
3. **Level 3**: 需要重新設計架構或技術棧的問題

### 交付檢查清單
- [ ] 架構文檔完整 (專案架構總覽)
- [ ] 開發記錄完整 (Claude_Code完成工作記錄)  
- [ ] 實作記錄完整 (Cursor完成工作記錄)
- [ ] 協作流程文檔 (Claude_Cursor協作指南)
- [ ] 所有代碼通過質量檢查
- [ ] 測試覆蓋率達標
- [ ] 性能指標符合要求

---

## 🗂️ 專案檔案結構標準

```
veeva-data-quality-system/
├── .vscode/                    # VS Code設定檔
│   ├── settings.json
│   └── extensions.json
├── sql/                        # 所有SQL檔案
│   ├── 01_schema/
│   │   ├── create_tables.sql
│   │   ├── create_indexes.sql
│   │   └── create_constraints.sql
│   ├── 02_validation/
│   │   ├── completeness_checks.sql
│   │   ├── consistency_checks.sql
│   │   ├── accuracy_checks.sql
│   │   └── relationship_checks.sql
│   ├── 03_reconciliation/
│   │   ├── matching_logic.sql
│   │   ├── golden_record_creation.sql
│   │   └── conflict_resolution.sql
│   ├── 04_incremental/
│   │   ├── change_tracking.sql
│   │   ├── incremental_load.sql
│   │   └── rollback_procedures.sql
│   ├── 05_business_rules/
│   │   ├── rule_definitions.sql
│   │   └── rule_violations.sql
│   └── 06_reporting/
│       ├── quality_metrics.sql
│       └── reconciliation_report.sql
├── python/                     # Python程式碼
│   ├── __init__.py
│   ├── pipeline/              # ETL主要邏輯
│   │   ├── __init__.py
│   │   ├── data_loader.py
│   │   ├── validator.py
│   │   ├── reconciler.py
│   │   └── incremental_processor.py
│   ├── models/                # 資料模型定義
│   │   ├── __init__.py
│   │   ├── author.py
│   │   ├── institution.py
│   │   └── publication.py
│   ├── utils/                 # 共用工具函數
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── logging_config.py
│   │   └── data_quality.py
│   ├── config/                # 設定檔管理
│   │   ├── __init__.py
│   │   ├── database_config.py
│   │   └── pipeline_config.yaml
│   └── main.py                # 主程式進入點
├── tests/                     # 測試檔案
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_validator.py
│   │   ├── test_reconciler.py
│   │   └── test_utils.py
│   ├── integration/
│   │   ├── test_pipeline.py
│   │   └── test_database.py
│   └── performance/
│       └── test_large_dataset.py
├── data/                      # 資料檔案
│   ├── raw/                   # 原始資料
│   ├── processed/             # 處理後資料
│   └── database/              # 資料庫檔案
│       └── veeva_opendata.db
├── docs/                      # 文檔
│   ├── architecture.md
│   ├── data_dictionary.md
│   ├── api_reference.md
│   └── deployment_guide.md
├── reports/                   # 產出報表
│   ├── quality_metrics/
│   └── reconciliation/
├── requirements.txt           # Python套件需求
├── setup.py                   # 套件安裝設定
├── .gitignore                 # Git忽略檔案
├── .env.example               # 環境變數範例
├── README.md                  # 專案說明
└── CHANGELOG.md               # 變更記錄
```

---

## 📋 Claude Code 負責項目

### 第一階段：專案規劃與設計
- [x] 專案需求分析和架構設計
- [x] 資料模型設計和schema定義
- [x] 檔案結構規劃
- [ ] 主要SQL查詢邏輯設計
- [ ] 資料品質框架規劃
- [ ] 商業規則定義

### 第二階段：核心邏輯實作
- [ ] 複雜SQL查詢撰寫（20個驗證查詢）
- [ ] 資料整合邏輯設計
- [ ] 增量更新策略實作
- [ ] 商業規則引擎設計
- [ ] 效能優化策略

### 第三階段：整合與測試
- [ ] 端到端流程整合
- [ ] 效能測試設計
- [ ] 文檔撰寫
- [ ] 展示材料準備

---

## 🔧 Cursor AI 負責項目

### 程式碼實作細節
- [ ] Python模組實作
- [ ] 設定檔管理系統
- [ ] 錯誤處理和日誌記錄
- [ ] 單元測試撰寫
- [ ] 程式碼重構和優化

### 開發工具和環境
- [ ] VS Code設定優化
- [ ] 程式碼格式化和linting
- [ ] Git hooks設置
- [ ] 虛擬環境管理
- [ ] 持續整合設置

### 除錯和優化
- [ ] 效能瓶頸分析
- [ ] 記憶體使用優化
- [ ] SQL查詢效能調校
- [ ] 錯誤追蹤和修復

---

## 🔄 協作工作流程

### Day 1: 基礎建設
#### Claude Code 任務
1. 設計完整的資料庫schema
2. 撰寫DDL SQL腳本
3. 規劃資料匯入邏輯
4. 設計基本驗證查詢

#### Cursor AI 任務
1. 實作Python資料載入器
2. 建立資料庫連線管理
3. 實作基本的CRUD操作
4. 設置專案環境和依賴

#### 協作點
- Claude Code提供SQL schema → Cursor實作Python ORM模型
- Claude Code設計查詢邏輯 → Cursor實作查詢執行器

### Day 2: 資料品質系統
#### Claude Code 任務
1. 撰寫20個複雜驗證查詢
2. 設計品質評分算法
3. 規劃異常偵測邏輯
4. 建立報表查詢模板

#### Cursor AI 任務
1. 實作查詢執行引擎
2. 建立品質指標計算模組
3. 實作報表產生器
4. 建立異常警報系統

### Day 3: 資料整合
#### Claude Code 任務
1. 設計matching演算法邏輯
2. 撰寫reconciliation SQL
3. 定義衝突解決規則
4. 設計Golden Record邏輯

#### Cursor AI 任務
1. 實作matching演算法
2. 建立衝突解決引擎
3. 實作資料合併邏輯
4. 建立整合測試

### Day 4-6: 增量更新與商業規則
#### 繼續相同協作模式...

---

## 📚 程式碼標準與規範

### Python編碼標準
```python
# 檔案頭部註解模板
"""
Module: data_validator.py
Purpose: Data quality validation engine for Veeva OpenData simulation
Author: Claude Code + Cursor AI
Created: 2025-08-07
Last Modified: 2025-08-07
"""

# 匯入順序
import os
import sys
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import sqlite3
from sqlalchemy import create_engine

# 類別定義標準
@dataclass
class ValidationResult:
    """資料驗證結果"""
    rule_name: str
    passed: bool
    error_count: int
    error_details: Optional[Dict] = None
    execution_time: Optional[float] = None

# 函數定義標準
def validate_data_completeness(
    table_name: str,
    required_columns: List[str],
    connection: sqlite3.Connection
) -> ValidationResult:
    """
    檢查資料完整性
    
    Args:
        table_name: 待檢查的表名
        required_columns: 必填欄位清單
        connection: 資料庫連線
        
    Returns:
        ValidationResult: 驗證結果物件
        
    Raises:
        DatabaseError: 當資料庫查詢失敗時
    """
    pass
```

### SQL編碼標準
```sql
-- 檔案頭部註解模板
/*
File: completeness_checks.sql
Purpose: Data completeness validation queries
Author: Claude Code
Created: 2025-08-07
Last Modified: 2025-08-07
Description: 檢查資料完整性的SQL查詢集合
*/

-- 查詢標準格式
-- Query 1: 檢查作者資料完整性
WITH author_completeness AS (
    SELECT 
        COUNT(*) as total_records,
        SUM(CASE WHEN author_name IS NULL OR author_name = '' THEN 1 ELSE 0 END) as missing_name,
        SUM(CASE WHEN email IS NULL OR email = '' THEN 1 ELSE 0 END) as missing_email,
        SUM(CASE WHEN orcid IS NULL OR orcid = '' THEN 1 ELSE 0 END) as missing_orcid
    FROM dim_authors
    WHERE is_golden_record = TRUE
)
SELECT 
    'author_completeness' as rule_name,
    total_records,
    ROUND(100.0 * (total_records - missing_name) / total_records, 2) as name_completeness_pct,
    ROUND(100.0 * (total_records - missing_email) / total_records, 2) as email_completeness_pct,
    ROUND(100.0 * (total_records - missing_orcid) / total_records, 2) as orcid_completeness_pct,
    CASE 
        WHEN (total_records - missing_name) / total_records >= 0.95 THEN 'PASS'
        ELSE 'FAIL'
    END as validation_status
FROM author_completeness;
```

---

## 🔀 Git 協作流程

### 分支策略
```
main              # 主分支，穩定版本
├── develop       # 開發分支，整合功能
├── feature/day1-database-setup     # Claude Code 功能分支
├── feature/day1-python-loader      # Cursor AI 功能分支
├── feature/day2-sql-validation     # Claude Code 功能分支
└── feature/day2-validation-engine  # Cursor AI 功能分支
```

### Commit 訊息標準
```
<type>(<scope>): <subject>

<body>

<footer>
```

範例：
```
feat(sql): add data completeness validation queries

- Implemented 5 completeness check queries for dim_authors
- Added email format validation
- Created ORCID existence check
- Added comprehensive test cases

Closes #12
```

### 協作檢查點
1. **每日同步**: 早上對齊當天工作，晚上檢討進度
2. **功能完成**: 每個功能完成後立即code review
3. **整合測試**: 每兩天進行整合測試
4. **文檔更新**: 程式碼變更後立即更新文檔

---

## 📊 品質控制檢查清單

### 程式碼品質
- [ ] 所有函數都有docstring
- [ ] 變數命名具有意義
- [ ] 錯誤處理完善
- [ ] 單元測試覆蓋率 > 80%
- [ ] 無未使用的匯入
- [ ] 符合PEP8標準

### SQL品質
- [ ] 所有查詢都有註解說明
- [ ] 使用標準化格式
- [ ] 避免SELECT *
- [ ] 適當使用索引提示
- [ ] 查詢效能測試通過

### 文檔品質
- [ ] README完整且清晰
- [ ] API文檔自動生成
- [ ] 架構圖表清楚
- [ ] 部署指南詳細
- [ ] 故障排除指南完整

---

## 🚀 最終交付檢查

### 技術要求
- [x] 專案架構設計完整
- [ ] 20個以上複雜SQL查詢
- [ ] 完整的資料品質框架
- [ ] 增量更新機制
- [ ] 商業規則實作
- [ ] 效能測試報告

### 文檔要求
- [ ] 技術架構文檔
- [ ] 使用者操作指南
- [ ] API參考文檔
- [ ] 部署說明文檔
- [ ] 展示簡報材料

### 展示準備
- [ ] GitHub repository整理
- [ ] 演示環境設置
- [ ] 關鍵功能展示腳本
- [ ] Q&A常見問題準備
- [ ] 技術細節深入解釋

---

## 💡 協作提醒

### Claude Code 專長發揮
- 複雜邏輯設計和規劃能力
- SQL查詢優化和最佳實務
- 系統架構設計經驗
- 商業需求理解和轉換

### Cursor AI 專長發揮  
- 程式碼實作和除錯效率
- 開發工具整合和優化
- 效能調校和重構能力
- 測試自動化和CI/CD

### 避免重複工作
1. 明確定義交接點和界面
2. 及時溝通設計變更
3. 保持代碼庫同步
4. 定期檢視和調整分工

這個協作指南將確保Claude Code和Cursor AI能夠發揮各自優勢，高效完成Veeva OpenData模擬系統的開發工作。