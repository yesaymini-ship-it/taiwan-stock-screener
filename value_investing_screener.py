<!-- ========================================== -->
<!-- 最後修改時間：2026-03-22 10:40 -->
<!-- ========================================== -->
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>我的專屬選股儀表板</title>
    <!-- 引入 Tailwind CSS 進行快速網頁排版與美化 -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- 引入 FontAwesome 圖示 -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        /* 簡單的自訂動畫與捲軸美化 */
        body { background-color: #f3f4f6; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .fade-in { animation: fadeIn 0.5s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #f1f1f1; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
    </style>
</head>
<body class="text-gray-800">

    <div class="max-w-6xl mx-auto p-4 sm:p-6 lg:p-8">
        <!-- 頁首區塊 -->
        <header class="flex items-center justify-between mb-8 pb-4 border-b border-gray-200 fade-in">
            <div>
                <h1 class="text-3xl font-bold text-indigo-700 flex items-center gap-2">
                    <i class="fa-solid fa-chart-line"></i> 價值投資選股系統
                </h1>
                <p class="text-gray-500 mt-1">自訂策略篩選，找出被低估的優質好股</p>
            </div>
            <div class="hidden sm:block text-sm text-gray-400">
                <p>最後更新時間：2026-03-22 10:40</p>
                <p>資料來源：模擬台股盤後數據</p>
            </div>
        </header>

        <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
            
            <!-- 左側：篩選條件控制面板 -->
            <div class="lg:col-span-1 bg-white rounded-xl shadow-sm border border-gray-100 p-5 fade-in">
                <h2 class="text-lg font-semibold mb-4 border-b pb-2"><i class="fa-solid fa-filter text-indigo-500"></i> 設定篩選條件</h2>
                
                <div class="space-y-5">
                    <!-- 條件 1：本益比 -->
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">本益比 (P/E) 低於</label>
                        <div class="flex items-center gap-2">
                            <input type="range" id="peRange" min="5" max="30" value="15" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer" oninput="document.getElementById('peValue').innerText = this.value">
                            <span id="peValue" class="text-sm font-bold w-8 text-right text-indigo-600">15</span>
                        </div>
                        <p class="text-xs text-gray-400 mt-1">尋找價格相對便宜的股票</p>
                    </div>

                    <!-- 條件 2：殖利率 -->
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">現金殖利率 高於 (%)</label>
                        <div class="flex items-center gap-2">
                            <input type="range" id="yieldRange" min="0" max="10" step="0.5" value="4.0" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer" oninput="document.getElementById('yieldValue').innerText = this.value">
                            <span id="yieldValue" class="text-sm font-bold w-8 text-right text-indigo-600">4.0</span>
                        </div>
                        <p class="text-xs text-gray-400 mt-1">確保每年有穩定的股息收入</p>
                    </div>

                    <!-- 條件 3：EPS成長 -->
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">基本面指標</label>
                        <label class="flex items-center space-x-2 cursor-pointer">
                            <input type="checkbox" id="epsGrowth" checked class="rounded text-indigo-600 focus:ring-indigo-500">
                            <span class="text-sm text-gray-700">近四季 EPS 大於去年同期</span>
                        </label>
                    </div>

                    <button onclick="runFilter()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-4 rounded-lg transition-colors duration-200 shadow-sm flex justify-center items-center gap-2 mt-4">
                        <i class="fa-solid fa-play"></i> 執行策略選股
                    </button>
                </div>
            </div>

            <!-- 右側：選股結果呈現區塊 -->
            <div class="lg:col-span-3 bg-white rounded-xl shadow-sm border border-gray-100 p-5 fade-in" style="animation-delay: 0.1s;">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-lg font-semibold"><i class="fa-solid fa-list-check text-green-500"></i> 符合條件的股票清單</h2>
                    <span id="resultCount" class="bg-green-100 text-green-800 text-xs font-medium px-2.5 py-0.5 rounded-full">共 0 檔</span>
                </div>

                <!-- 模擬資料載入中的動畫 -->
                <div id="loading" class="hidden flex-col items-center justify-center py-12">
                    <i class="fa-solid fa-circle-notch fa-spin text-3xl text-indigo-500 mb-3"></i>
                    <p class="text-gray-500">系統正在掃描全市場數據...</p>
                </div>

                <!-- 股票表格 -->
                <div id="tableContainer" class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">代號/名稱</th>
                                <th scope="col" class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">收盤價</th>
                                <th scope="col" class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">本益比 (P/E)</th>
                                <th scope="col" class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">殖利率</th>
                                <th scope="col" class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">EPS成長</th>
                                <th scope="col" class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                            </tr>
                        </thead>
                        <tbody id="stockTableBody" class="bg-white divide-y divide-gray-200">
                            <!-- JS 動態產生資料 -->
                        </tbody>
                    </table>
                </div>
                
                <!-- 無結果提示 -->
                <div id="noDataMsg" class="hidden text-center py-10 text-gray-500">
                    <i class="fa-regular fa-folder-open text-4xl mb-2 text-gray-300"></i>
                    <p>目前沒有符合條件的股票，請嘗試放寬篩選標準。</p>
                </div>
            </div>
        </div>
    </div>

    <!-- 顯示訊息的輕量化提示框 -->
    <div id="toast" class="fixed bottom-5 right-5 bg-gray-800 text-white px-4 py-2 rounded shadow-lg transform translate-y-20 opacity-0 transition-all duration-300">
        已複製代號！
    </div>

    <script>
        // 模擬台股資料庫 (在真實開發中，這些資料會透過 Python 爬蟲或 API 取得)
        const mockDatabase = [
            { id: '2330', name: '台積電', price: 780.0, pe: 18.5, yield: 2.1, epsGrowth: true },
            { id: '2317', name: '鴻海', price: 145.5, pe: 12.8, yield: 4.5, epsGrowth: true },
            { id: '2454', name: '聯發科', price: 1050.0, pe: 16.2, yield: 5.2, epsGrowth: false },
            { id: '2881', name: '富邦金', price: 68.2, pe: 10.5, yield: 5.8, epsGrowth: true },
            { id: '2882', name: '國泰金', price: 48.5, pe: 9.8, yield: 4.9, epsGrowth: true },
            { id: '1101', name: '台泥', price: 32.1, pe: 14.2, yield: 6.5, epsGrowth: false },
            { id: '2002', name: '中鋼', price: 24.5, pe: 22.1, yield: 3.2, epsGrowth: false },
            { id: '3231', name: '緯創', price: 115.0, pe: 14.5, yield: 3.8, epsGrowth: true },
            { id: '2308', name: '台達電', price: 340.5, pe: 20.1, yield: 3.0, epsGrowth: true },
            { id: '2891', name: '中信金', price: 31.8, pe: 11.2, yield: 6.1, epsGrowth: true }
        ];

        // 執行篩選的核心邏輯
        function runFilter() {
            // 取得使用者設定的條件
            const maxPe = parseFloat(document.getElementById('peRange').value);
            const minYield = parseFloat(document.getElementById('yieldRange').value);
            const requireEpsGrowth = document.getElementById('epsGrowth').checked;

            // UI 狀態切換：顯示載入中
            document.getElementById('tableContainer').classList.add('hidden');
            document.getElementById('noDataMsg').classList.add('hidden');
            document.getElementById('loading').classList.remove('hidden');
            document.getElementById('resultCount').innerText = '計算中...';

            // 模擬程式運算延遲 (0.8秒)
            setTimeout(() => {
                // 核心過濾器：將陣列中不符合條件的股票剔除
                const filteredStocks = mockDatabase.filter(stock => {
                    let passPE = stock.pe <= maxPe;
                    let passYield = stock.yield >= minYield;
                    let passEPS = requireEpsGrowth ? stock.epsGrowth === true : true;
                    return passPE && passYield && passEPS;
                });

                renderTable(filteredStocks);
                
                // UI 狀態切換：顯示結果
                document.getElementById('loading').classList.add('hidden');
                
                if(filteredStocks.length > 0) {
                    document.getElementById('tableContainer').classList.remove('hidden');
                } else {
                    document.getElementById('noDataMsg').classList.remove('hidden');
                }
                
                document.getElementById('resultCount').innerText = `共 ${filteredStocks.length} 檔`;
            }, 800);
        }

        // 將資料渲染成 HTML 表格
        function renderTable(stocks) {
            const tbody = document.getElementById('stockTableBody');
            tbody.innerHTML = ''; // 清空現有資料

            stocks.forEach((stock, index) => {
                // 決定 EPS 成長的圖示顏色
                const epsIcon = stock.epsGrowth 
                    ? '<i class="fa-solid fa-check text-green-500"></i>' 
                    : '<i class="fa-solid fa-xmark text-red-500"></i>';

                const row = `
                    <tr class="hover:bg-gray-50 transition-colors fade-in" style="animation-delay: ${index * 0.05}s">
                        <td class="px-4 py-4 whitespace-nowrap">
                            <div class="flex items-center">
                                <div class="text-sm font-bold text-gray-900">${stock.id}</div>
                                <div class="ml-2 text-sm text-gray-500">${stock.name}</div>
                            </div>
                        </td>
                        <td class="px-4 py-4 whitespace-nowrap text-right text-sm font-medium text-gray-900">
                            ${stock.price.toFixed(1)}
                        </td>
                        <td class="px-4 py-4 whitespace-nowrap text-right text-sm ${stock.pe < 12 ? 'text-green-600 font-bold' : 'text-gray-500'}">
                            ${stock.pe.toFixed(1)}
                        </td>
                        <td class="px-4 py-4 whitespace-nowrap text-right text-sm ${stock.yield > 5 ? 'text-red-500 font-bold' : 'text-gray-500'}">
                            ${stock.yield.toFixed(1)}%
                        </td>
                        <td class="px-4 py-4 whitespace-nowrap text-center text-sm">
                            ${epsIcon}
                        </td>
                        <td class="px-4 py-4 whitespace-nowrap text-center text-sm font-medium">
                            <button onclick="copyToClipboard('${stock.id}')" class="text-indigo-600 hover:text-indigo-900 bg-indigo-50 hover:bg-indigo-100 px-3 py-1 rounded-md transition-colors">
                                <i class="fa-regular fa-copy"></i> 代號
                            </button>
                        </td>
                    </tr>
                `;
                tbody.insertAdjacentHTML('beforeend', row);
            });
        }

        // 輔助功能：複製代號
        function copyToClipboard(text) {
            const tempInput = document.createElement("input");
            tempInput.value = text;
            document.body.appendChild(tempInput);
            tempInput.select();
            document.execCommand("copy");
            document.body.removeChild(tempInput);
            
            // 顯示提示
            const toast = document.getElementById('toast');
            toast.innerText = `已複製 ${text}`;
            toast.classList.remove('translate-y-20', 'opacity-0');
            
            setTimeout(() => {
                toast.classList.add('translate-y-20', 'opacity-0');
            }, 2000);
        }

        // 頁面載入時，預先執行一次篩選
        window.onload = runFilter;
    </script>
</body>
</html>
