import React from 'react';

/**
 * Отрисовывает канонический ГОСТ / ISA векторный символ промышленного оборудования.
 */
export default function GostIcon({ type, className = "w-10 h-10 text-cyan-400", active = false }) {
  const strokeColor = active ? "#22c55e" : "currentColor";
  const fillColor = active ? "rgba(34, 197, 94, 0.15)" : "rgba(30, 41, 59, 0.5)";

  switch (type) {
    // 1. Ёмкости и аппараты
    case 'tank_vertical':
      return (
        <svg viewBox="0 0 60 70" className={className} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          {/* Вертикальный цилиндр со скругленными днищами */}
          <path d="M 12 20 C 12 12, 48 12, 48 20 L 48 50 C 48 58, 12 58, 12 50 Z" fill={fillColor} />
          {/* Опоры */}
          <line x1="16" y1="56" x2="16" y2="65" />
          <line x1="44" y1="56" x2="44" y2="65" />
          {/* Линия уровня */}
          <line x1="20" y1="36" x2="40" y2="36" strokeDasharray="3 3" opacity="0.7" />
        </svg>
      );

    case 'tank_horizontal':
      return (
        <svg viewBox="0 0 80 50" className={className} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          {/* Горизонтальная цистерна */}
          <path d="M 22 12 L 58 12 C 68 12, 68 38, 58 38 L 22 38 C 12 38, 12 12, 22 12 Z" fill={fillColor} />
          {/* Опоры */}
          <line x1="26" y1="38" x2="22" y2="45" />
          <line x1="54" y1="38" x2="58" y2="45" />
        </svg>
      );

    case 'boiler':
      return (
        <svg viewBox="0 0 60 70" className={className} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          {/* Корпус котла */}
          <rect x="12" y="10" width="36" height="42" rx="4" fill={fillColor} />
          {/* Дымоход */}
          <path d="M 26 10 L 26 4 L 34 4 L 34 10" />
          {/* Символ пламени / горелки */}
          <path d="M 30 44 C 25 40, 25 32, 30 26 C 35 32, 35 40, 30 44 Z" fill={active ? "#f59e0b" : "currentColor"} opacity="0.9" />
          {/* Опоры */}
          <line x1="16" y1="52" x2="12" y2="62" />
          <line x1="44" y1="52" x2="48" y2="62" />
        </svg>
      );

    // 2. Гидравлика и приводы
    case 'pump':
      return (
        <svg viewBox="0 0 60 60" className={className} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          {/* Окружность насоса по ГОСТ 2.782 */}
          <circle cx="30" cy="30" r="18" fill={fillColor} />
          {/* Направленный треугольник подачи потока */}
          <polygon points="30,12 44,38 16,38" fill={active ? "#22c55e" : "currentColor"} />
          {/* Патрубки */}
          <line x1="30" y1="12" x2="30" y2="4" />
          <line x1="4" y1="30" x2="12" y2="30" />
        </svg>
      );

    case 'fan':
      return (
        <svg viewBox="0 0 60 60" className={className} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="30" cy="30" r="20" fill={fillColor} />
          {/* Лопасти вентилятора по ГОСТ 2.780 */}
          <path d="M 30 30 C 30 18, 42 18, 42 30 C 42 42, 30 42, 30 30 Z" opacity="0.8" fill="currentColor" />
          <path d="M 30 30 C 18 30, 18 42, 30 42 C 42 42, 42 30, 30 30 Z" opacity="0.8" fill="currentColor" />
          <circle cx="30" cy="30" r="4" fill="#0f172a" />
        </svg>
      );

    case 'motor':
      return (
        <svg viewBox="0 0 60 60" className={className} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="30" cy="30" r="18" fill={fillColor} />
          {/* Литера "M" по ГОСТ 2.780 */}
          <text x="30" y="38" fontSize="20" fontWeight="bold" textAnchor="middle" fill="currentColor" stroke="none">M</text>
        </svg>
      );

    // 3. Трубопроводная арматура
    case 'valve':
      return (
        <svg viewBox="0 0 60 50" className={className} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          {/* Два треугольника («песочные часы») по ГОСТ 2.784 */}
          <polygon points="12,14 30,26 12,38" fill={fillColor} />
          <polygon points="48,14 30,26 48,38" fill={fillColor} />
          {/* Шток и маховик */}
          <line x1="30" y1="26" x2="30" y2="10" />
          <line x1="22" y1="10" x2="38" y2="10" />
        </svg>
      );

    case 'control_valve':
      return (
        <svg viewBox="0 0 60 60" className={className} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          {/* Бабочка клапана */}
          <polygon points="12,28 30,38 12,48" fill={fillColor} />
          <polygon points="48,28 30,38 48,48" fill={fillColor} />
          {/* Шток */}
          <line x1="30" y1="38" x2="30" y2="18" />
          {/* Мембранный привод (грибок) по ГОСТ 2.784 */}
          <path d="M 16 18 C 16 8, 44 8, 44 18 Z" fill={fillColor} />
        </svg>
      );

    case 'gate_valve':
      return (
        <svg viewBox="0 0 60 60" className={className} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="12,28 30,38 12,48" fill={fillColor} />
          <polygon points="48,28 30,38 48,48" fill={fillColor} />
          {/* Задвижка с клином */}
          <line x1="30" y1="38" x2="30" y2="12" />
          <rect x="22" y="8" width="16" height="6" rx="2" fill="currentColor" />
        </svg>
      );

    // 4. Теплообмен
    case 'heat_exchanger':
      return (
        <svg viewBox="0 0 70 50" className={className} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <rect x="10" y="10" width="50" height="30" rx="6" fill={fillColor} />
          {/* Змеевик теплообменника */}
          <path d="M 18 25 Q 26 15 35 25 T 52 25" strokeWidth="2.5" />
          <line x1="6" y1="20" x2="10" y2="20" />
          <line x1="60" y1="30" x2="64" y2="30" />
        </svg>
      );

    case 'heater':
      return (
        <svg viewBox="0 0 60 60" className={className} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          {/* Электрический ТЭН - спираль нагревателя */}
          <path d="M 14 16 L 20 44 L 28 16 L 36 44 L 44 16 L 48 44" strokeWidth="2.8" />
          <circle cx="14" cy="14" r="3" fill="currentColor" />
          <circle cx="48" cy="46" r="3" fill="currentColor" />
        </svg>
      );

    // 5. Приборы КИПиА (ГОСТ 21.404-93)
    case 'sensor_temp':
    case 'sensor_pressure':
    case 'sensor_level':
    case 'sensor_flow': {
      const letters = {
        sensor_temp: 'T',
        sensor_pressure: 'P',
        sensor_level: 'L',
        sensor_flow: 'F',
      };
      const letter = letters[type] || 'S';

      return (
        <svg viewBox="0 0 60 60" className={className} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          {/* Окружность датчика по ГОСТ 21.404-93 */}
          <circle cx="30" cy="30" r="20" fill={fillColor} />
          {/* Горизонтальная разделительная черта по ГОСТ */}
          <line x1="10" y1="30" x2="50" y2="30" strokeWidth="1.5" />
          {/* Буквенное обозначение измеряемой величины */}
          <text x="30" y="24" fontSize="16" fontWeight="bold" textAnchor="middle" fill="currentColor" stroke="none">
            {letter}
          </text>
          {/* Нижний сектор для номера контура */}
          <text x="30" y="44" fontSize="10" textAnchor="middle" fill="currentColor" opacity="0.75" stroke="none">
            01
          </text>
        </svg>
      );
    }

    // 6. Механика
    case 'conveyor':
      return (
        <svg viewBox="0 0 80 40" className={className} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          {/* Барабаны */}
          <circle cx="20" cy="20" r="9" fill={fillColor} />
          <circle cx="60" cy="20" r="9" fill={fillColor} />
          {/* Лента */}
          <line x1="20" y1="11" x2="60" y2="11" strokeWidth="3" />
          <line x1="20" y1="29" x2="60" y2="29" strokeWidth="3" />
          {/* Стрелка движения */}
          <polyline points="35,16 43,20 35,24" strokeWidth="2" />
        </svg>
      );

    default:
      return (
        <svg viewBox="0 0 50 50" className={className} fill="none" stroke={strokeColor} strokeWidth="2">
          <rect x="10" y="10" width="30" height="30" rx="4" fill={fillColor} />
          <text x="25" y="30" fontSize="12" textAnchor="middle" fill="currentColor" stroke="none">?</text>
        </svg>
      );
  }
}
