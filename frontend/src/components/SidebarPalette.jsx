import React, { useState } from 'react';
import { Search, Plus, Layers } from 'lucide-react';
import GostIcon from './GostIcon';
import { EQUIPMENT_CATEGORIES, EQUIPMENT_TYPES } from '../constants/equipmentCatalog';

export default function SidebarPalette({ onAddWidget }) {
  const [search, setSearch] = useState('');

  const filteredCategories = EQUIPMENT_CATEGORIES.map((cat) => {
    const items = Object.values(EQUIPMENT_TYPES).filter(
      (item) =>
        item.category === cat.id &&
        (item.title.toLowerCase().includes(search.toLowerCase()) ||
          item.standard.toLowerCase().includes(search.toLowerCase()) ||
          item.type.toLowerCase().includes(search.toLowerCase()))
    );
    return { ...cat, items };
  }).filter((cat) => cat.items.length > 0);

  return (
    <aside className="w-72 bg-slate-900 border-r border-slate-800 flex flex-col h-full shrink-0 select-none">
      {/* Шапка боковой панели */}
      <div className="p-3 border-b border-slate-800">
        <div className="flex items-center gap-2 mb-2 text-xs font-semibold text-slate-300 uppercase tracking-wider">
          <Layers className="w-4 h-4 text-cyan-400" />
          <span>Каталог оборудования</span>
        </div>
        
        {/* Поиск */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Поиск по ГОСТ или имени..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 pl-8 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
          />
        </div>
      </div>

      {/* Список категорий и компонентов */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {filteredCategories.map((cat) => (
          <div key={cat.id} className="space-y-1.5">
            <h3 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-1">
              {cat.title}
            </h3>

            <div className="grid grid-cols-1 gap-1.5">
              {cat.items.map((item) => (
                <div
                  key={item.type}
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.setData('text/plain', item.type);
                  }}
                  onClick={() => onAddWidget(item.type)}
                  className="flex items-center justify-between p-2 rounded-lg bg-slate-950/70 hover:bg-slate-800/80 border border-slate-800/80 hover:border-cyan-500/50 cursor-pointer transition-all group"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="w-9 h-9 rounded bg-slate-900 flex items-center justify-center p-1 border border-slate-800 shrink-0 group-hover:border-cyan-500/40">
                      <GostIcon type={item.type} className="w-full h-full text-cyan-400" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-slate-200 truncate group-hover:text-cyan-300">
                        {item.title}
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono">
                        {item.standard}
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    title="Добавить на схему"
                    className="p-1 rounded text-slate-500 hover:text-cyan-300 hover:bg-slate-700/50 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}

        {filteredCategories.length === 0 && (
          <div className="text-center py-8 text-xs text-slate-500">
            Ничего не найдено по запросу «{search}»
          </div>
        )}
      </div>

      {/* Футер палитры */}
      <div className="p-2.5 bg-slate-950/40 border-t border-slate-800 text-[10px] text-slate-500 text-center">
        Кликните на прибор или перетащите на холст
      </div>
    </aside>
  );
}
