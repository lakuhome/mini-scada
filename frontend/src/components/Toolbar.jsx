import React from 'react';
import { 
  Download, 
  Upload, 
  Trash2, 
  Sparkles, 
  Grid, 
  Cpu, 
  Sliders
} from 'lucide-react';

export default function Toolbar({
  title,
  setTitle,
  snapToGrid,
  setSnapToGrid,
  onResetDemo,
  onClear,
  onOpenExport,
  onOpenImport,
  widgetCount,
}) {
  return (
    <header className="h-14 bg-slate-900 border-b border-slate-800 px-4 flex items-center justify-between z-20 shrink-0">
      {/* Логотип и Название */}
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-cyan-600/20 text-cyan-400 border border-cyan-500/30">
          <Cpu className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm tracking-wide text-slate-100">mini-scada</span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-cyan-900/50 text-cyan-300 border border-cyan-700/50 font-mono">
              HMI Designer
            </span>
          </div>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="text-xs text-slate-400 hover:text-slate-200 focus:text-slate-100 bg-transparent border-b border-transparent hover:border-slate-700 focus:border-cyan-500 outline-none w-64 transition-colors"
            placeholder="Название мнемосхемы..."
          />
        </div>
      </div>

      {/* Быстрая статистика */}
      <div className="hidden md:flex items-center gap-4 text-xs text-slate-400">
        <span className="flex items-center gap-1.5 bg-slate-800/60 px-2.5 py-1 rounded-full border border-slate-700/50">
          <Sliders className="w-3.5 h-3.5 text-cyan-400" />
          Элементов на схеме: <strong className="text-slate-200">{widgetCount}</strong>
        </span>
      </div>

      {/* Кнопки управления */}
      <div className="flex items-center gap-2">
        {/* Переключатель сетки */}
        <button
          onClick={() => setSnapToGrid(!snapToGrid)}
          title="Привязка к сетке (шаг 20px)"
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium border transition-colors ${
            snapToGrid
              ? 'bg-cyan-950/60 text-cyan-300 border-cyan-700'
              : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200'
          }`}
        >
          <Grid className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Сетка 20px</span>
        </button>

        {/* Пример схемы */}
        <button
          onClick={onResetDemo}
          title="Загрузить типовую схему котельной"
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
        >
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          <span className="hidden sm:inline">Пример</span>
        </button>

        {/* Очистить */}
        <button
          onClick={onClear}
          title="Очистить холст"
          className="p-1.5 rounded text-slate-400 hover:text-rose-400 hover:bg-slate-800 border border-transparent hover:border-slate-700 transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>

        <div className="h-5 w-px bg-slate-800 mx-1" />

        {/* Импорт */}
        <button
          onClick={onOpenImport}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
        >
          <Upload className="w-3.5 h-3.5" />
          <span>Импорт</span>
        </button>

        {/* Экспорт JSON */}
        <button
          onClick={onOpenExport}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg shadow-cyan-900/30 transition-all hover:shadow-cyan-800/50"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Экспорт JSON</span>
        </button>
      </div>
    </header>
  );
}
