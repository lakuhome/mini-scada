import React from 'react';
import { 
  Sliders, 
  Trash2, 
  Copy, 
  Tag as TagIcon, 
  Settings2,
  Maximize2
} from 'lucide-react';
import GostIcon from './GostIcon';
import { EQUIPMENT_TYPES, COMMON_SCADA_TAGS } from '../constants/equipmentCatalog';

export default function PropertiesPanel({
  selectedWidget,
  onUpdateWidget,
  onDeleteWidget,
  onDuplicateWidget,
}) {
  if (!selectedWidget) {
    return (
      <aside className="w-80 bg-slate-900 border-l border-slate-800 flex flex-col h-full shrink-0 select-none p-4 text-slate-500">
        <div className="flex items-center gap-2 mb-3 text-xs font-semibold text-slate-300 uppercase tracking-wider">
          <Settings2 className="w-4 h-4 text-cyan-400" />
          <span>Свойства элемента</span>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center text-center p-6 border-2 border-dashed border-slate-800/80 rounded-xl">
          <div className="w-12 h-12 rounded-full bg-slate-800/60 flex items-center justify-center mb-3 text-slate-500">
            <Sliders className="w-6 h-6" />
          </div>
          <p className="text-xs text-slate-400 font-medium mb-1">Элемент не выбран</p>
          <p className="text-[11px] text-slate-500">
            Выберите любой прибор на холсте, чтобы настроить его параметры и привязать к тегу Modbus.
          </p>
        </div>
      </aside>
    );
  }

  const meta = EQUIPMENT_TYPES[selectedWidget.type] || {};

  return (
    <aside className="w-80 bg-slate-900 border-l border-slate-800 flex flex-col h-full shrink-0 select-none">
      {/* Шапка инспектора */}
      <div className="p-3.5 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded bg-slate-950 flex items-center justify-center p-1 border border-slate-800 shrink-0">
            <GostIcon type={selectedWidget.type} className="w-full h-full text-cyan-400" />
          </div>
          <div className="min-w-0">
            <div className="text-xs font-semibold text-slate-200 truncate">
              {meta.title || selectedWidget.type}
            </div>
            <div className="text-[10px] text-slate-500 font-mono">
              {meta.standard || 'ГОСТ'}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={() => onDuplicateWidget(selectedWidget.id)}
            title="Дублировать элемент"
            className="p-1.5 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <Copy className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onDeleteWidget(selectedWidget.id)}
            title="Удалить со схемы (Del)"
            className="p-1.5 rounded text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Форма редактирования */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {/* Название */}
        <div className="space-y-1">
          <label className="text-[11px] font-medium text-slate-400">Название прибора</label>
          <input
            type="text"
            value={selectedWidget.title || ''}
            onChange={(e) => onUpdateWidget({ title: e.target.value })}
            className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500 transition-colors"
          />
        </div>

        {/* Уникальный ID */}
        <div className="space-y-1">
          <label className="text-[11px] font-medium text-slate-400">ID элемента в схеме</label>
          <input
            type="text"
            value={selectedWidget.id || ''}
            onChange={(e) => onUpdateWidget({ id: e.target.value })}
            className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-400 font-mono text-[11px] focus:outline-none focus:border-cyan-500 transition-colors"
          />
        </div>

        <div className="h-px bg-slate-800/80 my-2" />

        {/* Привязка к тегу телеметрии */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-[11px] font-medium text-cyan-400 flex items-center gap-1">
              <TagIcon className="w-3 h-3" />
              Тег опроса (FC 03)
            </label>
            <span className="text-[10px] text-slate-500 font-mono">InMemoryBus</span>
          </div>
          <input
            type="text"
            list="common-tags-list"
            value={selectedWidget.tag_id || ''}
            placeholder="например, Boiler_Temp_01"
            onChange={(e) => onUpdateWidget({ tag_id: e.target.value || null })}
            className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-mono text-[11px] focus:outline-none focus:border-cyan-500 transition-colors"
          />
          <datalist id="common-tags-list">
            {COMMON_SCADA_TAGS.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
          <p className="text-[10px] text-slate-500">
            Идентификатор тега в шине данных для чтения значений в реальном времени.
          </p>
        </div>

        {/* Тег уставки (если поддерживается) */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-[11px] font-medium text-amber-400">
              Тег уставки (FC 06)
            </label>
            <span className="text-[10px] text-slate-500 font-mono">Опционально</span>
          </div>
          <input
            type="text"
            value={selectedWidget.tag_setpoint || ''}
            placeholder="например, Temp_Setpoint_01"
            onChange={(e) => onUpdateWidget({ tag_setpoint: e.target.value || null })}
            className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-mono text-[11px] focus:outline-none focus:border-amber-500 transition-colors"
          />
        </div>

        <div className="h-px bg-slate-800/80 my-2" />

        {/* Единица измерения */}
        <div className="space-y-1">
          <label className="text-[11px] font-medium text-slate-400">Единица измерения</label>
          <input
            type="text"
            value={selectedWidget.unit || ''}
            placeholder="°C, бар, %, кВт..."
            onChange={(e) => onUpdateWidget({ unit: e.target.value })}
            className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500 transition-colors"
          />
        </div>

        {/* Диапазон (Min / Max) */}
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-slate-400">Мин. значение</label>
            <input
              type="number"
              value={selectedWidget.min_val ?? ''}
              onChange={(e) =>
                onUpdateWidget({
                  min_val: e.target.value === '' ? null : parseFloat(e.target.value),
                })
              }
              className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-mono text-[11px] focus:outline-none focus:border-cyan-500 transition-colors"
            />
          </div>
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-slate-400">Макс. значение</label>
            <input
              type="number"
              value={selectedWidget.max_val ?? ''}
              onChange={(e) =>
                onUpdateWidget({
                  max_val: e.target.value === '' ? null : parseFloat(e.target.value),
                })
              }
              className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-mono text-[11px] focus:outline-none focus:border-cyan-500 transition-colors"
            />
          </div>
        </div>

        <div className="h-px bg-slate-800/80 my-2" />

        {/* Координаты X, Y */}
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400">
            <Maximize2 className="w-3 h-3" />
            <span>Координаты на холсте (px)</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="text-[10px] text-slate-500">X:</span>
              <input
                type="number"
                value={selectedWidget.x}
                onChange={(e) => onUpdateWidget({ x: parseInt(e.target.value) || 0 })}
                className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-300 font-mono text-[11px]"
              />
            </div>
            <div>
              <span className="text-[10px] text-slate-500">Y:</span>
              <input
                type="number"
                value={selectedWidget.y}
                onChange={(e) => onUpdateWidget({ y: parseInt(e.target.value) || 0 })}
                className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-300 font-mono text-[11px]"
              />
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
