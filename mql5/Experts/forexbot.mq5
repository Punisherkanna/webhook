//+------------------------------------------------------------------+
//|                                                     forexbot.mq5  |
//|   Robot de trading Forex - DAY TRADING (sin overnight).          |
//|   Dos estrategias: Donchian breakout y MACD trend.               |
//|   Una sola posicion, stops por ATR. SIN grid/hedging/HFT/        |
//|   martingala. Proteccion para prop firm integrada.               |
//+------------------------------------------------------------------+
#property copyright "forexbot"
#property link      "https://github.com/Punisherkanna/webhook"
#property version   "2.00"
#property description "Forex EA day-trading: Donchian breakout + MACD trend."
#property strict

#include <Trade/Trade.mqh>

//--- Estrategia seleccionable (solo las dos mas robustas)
enum ENUM_STRATEGY
  {
   STRAT_DONCHIAN_BREAKOUT,   // Donchian breakout (ruptura de canal)
   STRAT_MACD_TREND           // MACD trend (momentum con filtro EMA)
  };

enum ENUM_SIGNAL { SIG_NONE, SIG_LONG, SIG_SHORT };

//--- Base de calculo del DD diario
enum ENUM_DAILY_BASE
  {
   DAILY_BASE_DAY_BALANCE,   // Balance al inicio del dia (estandar)
   DAILY_BASE_INITIAL        // Balance inicial fijo del desafio
  };

//============================ Parametros ============================
input group "General"
input ENUM_STRATEGY   InpStrategy   = STRAT_DONCHIAN_BREAKOUT; // Estrategia
input ENUM_TIMEFRAMES InpTimeframe  = PERIOD_CURRENT;          // Temporalidad (usa M5/M15)
input long            InpMagic      = 234000;                  // Numero magico
input bool            InpNewBarOnly = true;                    // Operar solo en vela cerrada
input ulong           InpDeviation  = 30;                      // Desviacion maxima (puntos)
input string          InpComment    = "forexbot";              // Comentario de orden

input group "Riesgo / dimensionamiento"
input double InpRiskPerTrade = 0.01;  // Riesgo por operacion (fraccion de equity, 0-1)
input double InpMaxLots      = 10.0;  // Lote maximo permitido
input int    InpMaxPositions = 1;     // Maximo de posiciones simultaneas (de este EA)

input group "Stops por ATR"
input int    InpAtrPeriod = 14;   // Periodo ATR
input double InpAtrStop    = 1.5; // Stop = ATR * este factor
input double InpAtrTarget  = 2.0; // Objetivo = ATR * este factor

input group "Day trading (sin overnight)"
input bool InpCloseEndOfDay = true;  // Cerrar todo al final del dia (no overnight)
input int  InpCloseHour     = 23;    // Hora de cierre (servidor)
input int  InpCloseMinute   = 30;    // Minuto de cierre
input bool InpUseSession    = false; // Limitar entradas a una franja horaria
input int  InpSessionStart  = 7;     // Inicio de sesion (hora servidor)
input int  InpSessionEnd    = 20;    // Fin de sesion (hora servidor)

input group "Donchian breakout"
input int  InpDonchianPeriod      = 20;   // Periodo del canal (velas previas)
input bool InpDonchianTrendFilter = true; // Solo operar a favor de la EMA de tendencia
input int  InpDonchianTrendPeriod = 100;  // EMA del filtro de tendencia (Donchian)

input group "MACD trend"
input int InpMacdFast        = 12;  // EMA rapida MACD
input int InpMacdSlow        = 26;  // EMA lenta MACD
input int InpMacdSignal      = 9;   // EMA de la senal MACD
input int InpMacdTrendPeriod = 100; // EMA del filtro de tendencia

input group "Gestion de la operacion (trailing)"
input bool   InpUseBreakEven   = true; // Mover SL a break-even
input double InpBreakEvenATR    = 1.0; // Activar BE tras este profit (en ATR)
input double InpBreakEvenLockATR = 0.1;// Bloqueo sobre la entrada al hacer BE (ATR)
input bool   InpUseTrailing     = true;// Trailing stop por ATR
input double InpTrailStartATR    = 1.5;// Empezar a seguir tras este profit (ATR)
input double InpTrailDistATR      = 2.0;// Distancia del trailing (ATR)

input group "Proteccion (prop firm)"
input bool   InpUseProtection     = true;  // Activar limites de proteccion
input double InpMaxFloatDDPct      = 1.9;   // Max DD de PnL flotante POR SIMBOLO (%)
input double InpMaxDailyDDPct      = 3.99;  // Max DD diario (%)
input double InpMaxTotalDDPct      = 10.0;  // Max DD total (%)
input ENUM_DAILY_BASE InpDailyBase = DAILY_BASE_DAY_BALANCE; // Base del DD diario/flotante
input double InpSafetyMarginPct    = 10.0;  // Margen de seguridad (% del limite)
input double InpDailyProfitTarget  = 100.0; // Objetivo de profit diario (moneda; 0=off)
input bool   InpCloseOnTarget      = true;  // Cerrar posiciones al lograr el objetivo
input bool   InpHaltDayOnFloat     = true;  // Tras cortar por flotante, pausar el dia
input bool   InpAlertOnBreach      = true;  // Avisar (Alert) al violar un limite
input bool   InpResetGuard         = false; // Reiniciar contadores (nuevo desafio)

input group "Panel visual"
input bool             InpShowPanel   = true;             // Mostrar panel
input int              InpPanelX      = 20;               // Posicion X (px)
input int              InpPanelY      = 30;               // Posicion Y (px)
input ENUM_BASE_CORNER InpPanelCorner = CORNER_LEFT_UPPER;// Esquina de anclaje
input color            InpAccent      = C'0,184,148';     // Color de acento

//--- Paleta del panel (tema oscuro profesional)
#define PFX     "fxbot_"
#define COL_TXT C'234,236,244'
#define COL_MUT C'140,146,166'
#define COL_GRN C'38,194,129'
#define COL_RED C'235,77,75'
#define COL_AMB C'240,180,40'
#define COL_SEP C'46,49,68'

//============================ Estado global ========================
CTrade          g_trade;
ENUM_TIMEFRAMES g_tf;
datetime        g_lastBar = 0;

int h_atr   = INVALID_HANDLE;
int h_macd  = INVALID_HANDLE;
int h_trend = INVALID_HANDLE;

//--- Estado de proteccion (persistido en variables globales del terminal)
double   g_refBalance      = 0.0;   // balance inicial (referencia del DD total)
double   g_dayStartBalance = 0.0;   // balance al inicio del dia (DD diario)
double   g_dayStartEquity  = 0.0;   // equity al inicio del dia (informativo)
datetime g_day             = 0;     // dia actual anclado
bool     g_haltTotal       = false; // bloqueo permanente por DD total
bool     g_haltDaily       = false; // bloqueo del dia por DD diario / flotante
string   g_gvRef, g_gvDay, g_gvDayBal, g_gvDayEq, g_gvHalt; // variables globales

//--- Ultimos valores de proteccion (para el panel)
double g_floatDDpct = 0.0, g_dailyDDpct = 0.0, g_totalDDpct = 0.0;
double g_dayProfit  = 0.0;   // profit del dia (equity - balance inicio de dia)
bool   g_targetHit  = false; // objetivo de profit diario alcanzado

//+------------------------------------------------------------------+
//| Utilidades de indicadores                                        |
//+------------------------------------------------------------------+
double IndVal(int handle, int buffer, int shift)
  {
   double v[];
   ArraySetAsSeries(v, true);
   if(handle == INVALID_HANDLE)
      return EMPTY_VALUE;
   if(CopyBuffer(handle, buffer, shift, 1, v) < 1)
      return EMPTY_VALUE;
   return v[0];
  }

bool Valid(double x)
  {
   return (x != EMPTY_VALUE && MathIsValidNumber(x));
  }

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_tf = (InpTimeframe == PERIOD_CURRENT) ? (ENUM_TIMEFRAMES)Period() : InpTimeframe;

   if(InpRiskPerTrade <= 0.0 || InpRiskPerTrade > 1.0)
     {
      Print("ERROR: InpRiskPerTrade debe estar en (0, 1]");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpStrategy == STRAT_MACD_TREND && InpMacdFast >= InpMacdSlow)
     {
      Print("ERROR: MACD rapida debe ser menor que lenta");
      return INIT_PARAMETERS_INCORRECT;
     }

   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(InpDeviation);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   h_atr = iATR(_Symbol, g_tf, InpAtrPeriod);
   if(h_atr == INVALID_HANDLE)
     {
      Print("ERROR: no se pudo crear el handle de ATR");
      return INIT_FAILED;
     }

   if(InpStrategy == STRAT_MACD_TREND)
     {
      h_macd  = iMACD(_Symbol, g_tf, InpMacdFast, InpMacdSlow, InpMacdSignal, PRICE_CLOSE);
      h_trend = iMA(_Symbol, g_tf, InpMacdTrendPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(h_macd == INVALID_HANDLE || h_trend == INVALID_HANDLE)
        {
         Print("ERROR: no se pudieron crear los indicadores de MACD");
         return INIT_FAILED;
        }
     }
   else if(InpStrategy == STRAT_DONCHIAN_BREAKOUT && InpDonchianTrendFilter)
     {
      h_trend = iMA(_Symbol, g_tf, InpDonchianTrendPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(h_trend == INVALID_HANDLE)
        {
         Print("ERROR: no se pudo crear la EMA de tendencia (Donchian)");
         return INIT_FAILED;
        }
     }

   PrintFormat("forexbot v2 iniciado: estrategia=%s  simbolo=%s  TF=%s",
               StratName(), _Symbol, TFString(g_tf));

   InitGuard();
   CreatePanel();
   UpdatePanel();
   if(InpShowPanel)
      EventSetTimer(1);

   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   int handles[] = {h_atr, h_macd, h_trend};
   for(int i = 0; i < ArraySize(handles); i++)
      if(handles[i] != INVALID_HANDLE)
         IndicatorRelease(handles[i]);

   EventKillTimer();
   ObjectsDeleteAll(0, PFX);
   ChartRedraw();
  }

//+------------------------------------------------------------------+
//| Helpers de tiempo / vela nueva / posiciones                      |
//+------------------------------------------------------------------+
bool IsNewBar()
  {
   datetime t = iTime(_Symbol, g_tf, 0);
   if(t != g_lastBar)
     {
      g_lastBar = t;
      return true;
     }
   return false;
  }

int CountMyPositions()
  {
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
         if(PositionGetInteger(POSITION_MAGIC) == InpMagic &&
            PositionGetString(POSITION_SYMBOL) == _Symbol)
            count++;
     }
   return count;
  }

//--- Day trading: ¿pasamos la hora de cierre del dia?
bool AfterDailyClose()
  {
   if(!InpCloseEndOfDay)
      return false;
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   int nowMin = t.hour * 60 + t.min;
   int clsMin = InpCloseHour * 60 + InpCloseMinute;
   return nowMin >= clsMin;
  }

//--- ¿Estamos dentro de la franja horaria permitida para entrar?
bool InSession()
  {
   if(!InpUseSession)
      return true;
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   int h = t.hour;
   if(InpSessionStart <= InpSessionEnd)
      return (h >= InpSessionStart && h < InpSessionEnd);
   return (h >= InpSessionStart || h < InpSessionEnd); // cruza medianoche
  }

//+------------------------------------------------------------------+
//| Senales (evaluadas en la vela cerrada, shift 1/2)                |
//+------------------------------------------------------------------+
ENUM_SIGNAL SignalDonchian()
  {
   if(Bars(_Symbol, g_tf) < InpDonchianPeriod + 3)
      return SIG_NONE;
   int idxH = iHighest(_Symbol, g_tf, MODE_HIGH, InpDonchianPeriod, 2);
   int idxL = iLowest(_Symbol, g_tf, MODE_LOW,  InpDonchianPeriod, 2);
   if(idxH < 0 || idxL < 0)
      return SIG_NONE;
   double upper = iHigh(_Symbol, g_tf, idxH);
   double lower = iLow(_Symbol, g_tf, idxL);
   double high1 = iHigh(_Symbol, g_tf, 1);
   double low1  = iLow(_Symbol, g_tf, 1);

   // Filtro de tendencia: solo romper a favor de la EMA.
   bool allowLong = true, allowShort = true;
   if(InpDonchianTrendFilter)
     {
      double ema = IndVal(h_trend, 0, 1);
      double c1  = iClose(_Symbol, g_tf, 1);
      if(!Valid(ema)) return SIG_NONE;
      allowLong  = (c1 > ema);
      allowShort = (c1 < ema);
     }

   if(high1 > upper && allowLong)  return SIG_LONG;
   if(low1  < lower && allowShort) return SIG_SHORT;
   return SIG_NONE;
  }

ENUM_SIGNAL SignalMACD()
  {
   double m1 = IndVal(h_macd, 0, 1), m2 = IndVal(h_macd, 0, 2);
   double g1 = IndVal(h_macd, 1, 1), g2 = IndVal(h_macd, 1, 2);
   double trend = IndVal(h_trend, 0, 1);
   if(!Valid(m1) || !Valid(m2) || !Valid(g1) || !Valid(g2) || !Valid(trend))
      return SIG_NONE;
   double price1 = iClose(_Symbol, g_tf, 1);
   bool up   = (m2 <= g2 && m1 > g1);
   bool down = (m2 >= g2 && m1 < g1);
   if(up && price1 > trend)   return SIG_LONG;
   if(down && price1 < trend) return SIG_SHORT;
   return SIG_NONE;
  }

ENUM_SIGNAL GetSignal()
  {
   if(InpStrategy == STRAT_MACD_TREND)
      return SignalMACD();
   return SignalDonchian();
  }

//+------------------------------------------------------------------+
//| Dimensionamiento por riesgo                                      |
//+------------------------------------------------------------------+
int VolumeDigits(double step)
  {
   int d = 0;
   while(step < 1.0 && d < 8) { step *= 10.0; d++; }
   return d;
  }

double CalcLots(double stopDistance)
  {
   if(stopDistance <= 0.0)
      return 0.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0.0 || tickValue <= 0.0)
      return 0.0;

   double moneyPerLot = (stopDistance / tickSize) * tickValue;
   if(moneyPerLot <= 0.0)
      return 0.0;

   double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskCash = equity * InpRiskPerTrade;
   double lots     = riskCash / moneyPerLot;

   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   maxLot = MathMin(maxLot, InpMaxLots);
   if(step <= 0.0)
      step = 0.01;

   lots = MathFloor(lots / step) * step;
   if(lots < minLot)
      return 0.0;
   if(lots > maxLot)
      lots = maxLot;
   return NormalizeDouble(lots, VolumeDigits(step));
  }

//+------------------------------------------------------------------+
//| Abrir operacion con SL/TP por ATR                                |
//+------------------------------------------------------------------+
void OpenTrade(ENUM_SIGNAL sig)
  {
   double atr = IndVal(h_atr, 0, 1);
   if(!Valid(atr) || atr <= 0.0)
     {
      Print("ATR no disponible, omito la entrada");
      return;
     }

   double point = _Point;
   long   stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist = stopsLevel * point;

   double stopDist = atr * InpAtrStop;
   double tgtDist  = atr * InpAtrTarget;
   if(stopDist < minDist) stopDist = minDist;
   if(tgtDist  < minDist) tgtDist  = minDist;

   double price, sl, tp;
   if(sig == SIG_LONG)
     {
      price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      sl = price - stopDist;
      tp = price + tgtDist;
     }
   else
     {
      price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      sl = price + stopDist;
      tp = price - tgtDist;
     }
   sl = NormalizeDouble(sl, _Digits);
   tp = NormalizeDouble(tp, _Digits);

   double lots = CalcLots(MathAbs(price - sl));
   if(lots <= 0.0)
     {
      Print("Lote calculado = 0 (riesgo/stop), omito la entrada");
      return;
     }

   bool ok;
   if(sig == SIG_LONG)
      ok = g_trade.Buy(lots, _Symbol, price, sl, tp, InpComment);
   else
      ok = g_trade.Sell(lots, _Symbol, price, sl, tp, InpComment);

   if(ok)
      PrintFormat("Orden %s %.2f lotes  SL=%.5f TP=%.5f",
                  (sig == SIG_LONG ? "BUY" : "SELL"), lots, sl, tp);
   else
      PrintFormat("Fallo al enviar la orden: ret=%d  %s",
                  g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
  }

//============================ Gestion de operacion abierta =========
//  Break-even y trailing stop por ATR. Ataca el problema de ganadoras
//  pequenas vs perdedoras grandes: protege ganancia y deja correr.
void ManageOpenPositions()
  {
   if(!InpUseBreakEven && !InpUseTrailing)
      return;
   double atr = IndVal(h_atr, 0, 1);
   if(!Valid(atr) || atr <= 0.0)
      return;

   double minDist = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      long   type  = PositionGetInteger(POSITION_TYPE);
      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl    = PositionGetDouble(POSITION_SL);
      double tp    = PositionGetDouble(POSITION_TP);
      double newSL = sl;

      if(type == POSITION_TYPE_BUY)
        {
         double profit = bid - entry;
         if(InpUseBreakEven && profit >= InpBreakEvenATR * atr)
           {
            double be = entry + InpBreakEvenLockATR * atr;
            if(be > newSL) newSL = be;
           }
         if(InpUseTrailing && profit >= InpTrailStartATR * atr)
           {
            double tr = bid - InpTrailDistATR * atr;
            if(tr > newSL) newSL = tr;
           }
         if(newSL > sl && (bid - newSL) >= minDist)
            g_trade.PositionModify(tk, NormalizeDouble(newSL, _Digits), tp);
        }
      else // SELL
        {
         double profit = entry - ask;
         if(InpUseBreakEven && profit >= InpBreakEvenATR * atr)
           {
            double be = entry - InpBreakEvenLockATR * atr;
            if(sl == 0.0 || be < newSL) newSL = be;
           }
         if(InpUseTrailing && profit >= InpTrailStartATR * atr)
           {
            double tr = ask + InpTrailDistATR * atr;
            if(sl == 0.0 || tr < newSL) newSL = tr;
           }
         if((sl == 0.0 || newSL < sl) && (newSL - ask) >= minDist)
            g_trade.PositionModify(tk, NormalizeDouble(newSL, _Digits), tp);
        }
     }
  }

//============================ Proteccion (prop firm) ===============
datetime TodayStart()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   return StructToTime(dt);
  }

void AnchorDay(datetime today)
  {
   g_day = today;
   g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   g_dayStartEquity  = AccountInfoDouble(ACCOUNT_EQUITY);
   g_haltDaily = false;
   GlobalVariableSet(g_gvDay,    (double)today);
   GlobalVariableSet(g_gvDayBal, g_dayStartBalance);
   GlobalVariableSet(g_gvDayEq,  g_dayStartEquity);
  }

void InitGuard()
  {
   if(!InpUseProtection)
      return;
   long acct = (long)AccountInfoInteger(ACCOUNT_LOGIN);
   string base = PFX + "guard_" + IntegerToString(acct) + "_"
               + IntegerToString(InpMagic) + "_";
   g_gvRef    = base + "ref";
   g_gvDay    = base + "day";
   g_gvDayBal = base + "daybal";
   g_gvDayEq  = base + "dayeq";
   g_gvHalt   = base + "halt";

   if(InpResetGuard)
     {
      GlobalVariableDel(g_gvRef);   GlobalVariableDel(g_gvDay);
      GlobalVariableDel(g_gvDayBal);GlobalVariableDel(g_gvDayEq);
      GlobalVariableDel(g_gvHalt);
      Print("PROTECCION: contadores reiniciados (nuevo desafio)");
     }

   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   if(GlobalVariableCheck(g_gvRef))
      g_refBalance = GlobalVariableGet(g_gvRef);
   else
     {
      g_refBalance = bal;
      GlobalVariableSet(g_gvRef, g_refBalance);
     }

   g_haltTotal = (GlobalVariableCheck(g_gvHalt) && GlobalVariableGet(g_gvHalt) > 0.5);

   datetime today = TodayStart();
   if(GlobalVariableCheck(g_gvDay) && (datetime)GlobalVariableGet(g_gvDay) == today
      && GlobalVariableCheck(g_gvDayBal) && GlobalVariableCheck(g_gvDayEq))
     {
      g_day = today;
      g_dayStartBalance = GlobalVariableGet(g_gvDayBal);
      g_dayStartEquity  = GlobalVariableGet(g_gvDayEq);
     }
   else
      AnchorDay(today);

   PrintFormat("PROTECCION activa: flot/simbolo=%.2f%%  diario=%.2f%%  total=%.2f%%  ref=%.2f",
               InpMaxFloatDDPct, InpMaxDailyDDPct, InpMaxTotalDDPct, g_refBalance);
  }

double SymbolFloatingPnl()
  {
   double pnl = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      pnl += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
     }
   return pnl;
  }

void CloseSymbolPositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      g_trade.PositionClose(tk);
     }
  }

void CloseAllMyPositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      g_trade.PositionClose(tk);
     }
  }

void Breach(string msg)
  {
   Print("PROTECCION: ", msg);
   if(InpAlertOnBreach)
      Alert(_Symbol + " forexbot - " + msg);
  }

bool RiskGuard()
  {
   datetime today = TodayStart();
   if(today != g_day)
      AnchorDay(today);

   double equity    = AccountInfoDouble(ACCOUNT_EQUITY);
   double baseTotal = (g_refBalance > 0.0 ? g_refBalance : AccountInfoDouble(ACCOUNT_BALANCE));
   double baseDay   = (InpDailyBase == DAILY_BASE_INITIAL)
                      ? baseTotal
                      : (g_dayStartBalance > 0.0 ? g_dayStartBalance : baseTotal);

   double keep = 1.0 - InpSafetyMarginPct / 100.0;
   if(keep < 0.0) keep = 0.0;

   double floatLimit = baseDay   * (InpMaxFloatDDPct / 100.0) * keep;
   double dailyLimit = baseDay   * (InpMaxDailyDDPct / 100.0) * keep;
   double totalLimit = baseTotal * (InpMaxTotalDDPct / 100.0) * keep;

   // 1) DD total (equity contra balance inicial)
   double totalDD = baseTotal - equity;
   g_totalDDpct = (baseTotal > 0.0 ? MathMax(0.0, totalDD) / baseTotal * 100.0 : 0.0);
   if(InpMaxTotalDDPct > 0.0 && totalDD >= totalLimit && !g_haltTotal)
     {
      g_haltTotal = true;
      GlobalVariableSet(g_gvHalt, 1.0);
      CloseAllMyPositions();
      Breach(StringFormat("DD TOTAL %.2f%% (corte %.2f%% de %.2f%%). Trading detenido.",
                          g_totalDDpct, InpMaxTotalDDPct * keep, InpMaxTotalDDPct));
     }

   // 2) DD diario (equity contra balance de inicio de dia)
   double dailyDD = baseDay - equity;
   g_dailyDDpct = (baseDay > 0.0 ? MathMax(0.0, dailyDD) / baseDay * 100.0 : 0.0);
   if(InpMaxDailyDDPct > 0.0 && dailyDD >= dailyLimit && !g_haltDaily)
     {
      g_haltDaily = true;
      CloseAllMyPositions();
      Breach(StringFormat("DD DIARIO %.2f%% (corte %.2f%% de %.2f%%). Pausa hasta manana.",
                          g_dailyDDpct, InpMaxDailyDDPct * keep, InpMaxDailyDDPct));
     }

   // 2b) Objetivo de profit diario
   double dayBase = (g_dayStartBalance > 0.0 ? g_dayStartBalance : baseTotal);
   g_dayProfit = equity - dayBase;
   g_targetHit = (InpDailyProfitTarget > 0.0 && g_dayProfit >= InpDailyProfitTarget);
   if(g_targetHit && !g_haltDaily)
     {
      g_haltDaily = true;
      if(InpCloseOnTarget)
         CloseAllMyPositions();
      Breach(StringFormat("OBJETIVO DIARIO +%.2f (meta %.2f). Pausa hasta manana.",
                          g_dayProfit, InpDailyProfitTarget));
     }

   // 3) DD de PnL flotante POR SIMBOLO
   double fpnl = SymbolFloatingPnl();
   g_floatDDpct = (baseDay > 0.0 && fpnl < 0.0 ? (-fpnl) / baseDay * 100.0 : 0.0);
   if(InpMaxFloatDDPct > 0.0 && fpnl < 0.0 && fpnl <= -floatLimit)
     {
      CloseSymbolPositions();
      Breach(StringFormat("DD FLOTANTE %s %.2f%% (corte %.2f%% de %.2f%%). Posiciones cerradas.",
                          _Symbol, g_floatDDpct, InpMaxFloatDDPct * keep, InpMaxFloatDDPct));
      if(InpHaltDayOnFloat)
         g_haltDaily = true;
     }

   return !(g_haltTotal || g_haltDaily);
  }

//============================ Panel visual =========================
string StratName()
  {
   if(InpStrategy == STRAT_MACD_TREND) return "MACD Trend";
   return "Donchian Breakout";
  }

string TFString(ENUM_TIMEFRAMES tf)
  {
   string s = EnumToString(tf);
   StringReplace(s, "PERIOD_", "");
   return s;
  }

//--- Bias direccional actual (estado de los indicadores)
ENUM_SIGNAL CurrentBias()
  {
   if(InpStrategy == STRAT_MACD_TREND)
     {
      double m = IndVal(h_macd, 0, 1), g = IndVal(h_macd, 1, 1);
      double tr = IndVal(h_trend, 0, 1);
      if(!Valid(m) || !Valid(g) || !Valid(tr)) return SIG_NONE;
      double c = iClose(_Symbol, g_tf, 1);
      if(m > g && c > tr) return SIG_LONG;
      if(m < g && c < tr) return SIG_SHORT;
      return SIG_NONE;
     }
   // Donchian: posicion del cierre dentro del canal previo
   int ih = iHighest(_Symbol, g_tf, MODE_HIGH, InpDonchianPeriod, 1);
   int il = iLowest(_Symbol, g_tf, MODE_LOW, InpDonchianPeriod, 1);
   if(ih < 0 || il < 0) return SIG_NONE;
   double up = iHigh(_Symbol, g_tf, ih), lo = iLow(_Symbol, g_tf, il);
   double c2 = iClose(_Symbol, g_tf, 1);
   return (c2 >= (up + lo) / 2.0) ? SIG_LONG : SIG_SHORT;
  }

double FloatingPnl(string &posDesc)
  {
   double pnl = 0.0;
   posDesc = "—";
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      pnl += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      long   type = PositionGetInteger(POSITION_TYPE);
      double vol  = PositionGetDouble(POSITION_VOLUME);
      double op   = PositionGetDouble(POSITION_PRICE_OPEN);
      posDesc = StringFormat("%s %.2f @ %s",
                             (type == POSITION_TYPE_BUY ? "BUY" : "SELL"),
                             vol, DoubleToString(op, _Digits));
     }
   return pnl;
  }

void HistoryStats(int &trades, double &realized)
  {
   trades = 0;
   realized = 0.0;
   if(!HistorySelect(0, TimeCurrent())) return;
   int deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
     {
      ulong t = HistoryDealGetTicket(i);
      if(t == 0) continue;
      if(HistoryDealGetInteger(t, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetString(t, DEAL_SYMBOL) != _Symbol) continue;
      realized += HistoryDealGetDouble(t, DEAL_PROFIT)
                + HistoryDealGetDouble(t, DEAL_SWAP)
                + HistoryDealGetDouble(t, DEAL_COMMISSION);
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(t, DEAL_ENTRY) == DEAL_ENTRY_OUT)
         trades++;
     }
  }

//--- Helpers de objetos graficos
void PRect(string nm, int x, int y, int w, int h, color bg)
  {
   string n = PFX + nm;
   if(ObjectFind(0, n) < 0) ObjectCreate(0, n, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, n, OBJPROP_CORNER, InpPanelCorner);
   ObjectSetInteger(0, n, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, n, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, n, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, n, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, n, OBJPROP_BGCOLOR, bg);
   ObjectSetInteger(0, n, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, n, OBJPROP_COLOR, bg);
   ObjectSetInteger(0, n, OBJPROP_BACK, false);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, n, OBJPROP_HIDDEN, true);
  }

void PLabel(string nm, int x, int y, string txt, color clr, int size,
            string font, ENUM_ANCHOR_POINT anchor)
  {
   string n = PFX + nm;
   if(ObjectFind(0, n) < 0) ObjectCreate(0, n, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, n, OBJPROP_CORNER, InpPanelCorner);
   ObjectSetInteger(0, n, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, n, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, n, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, n, OBJPROP_TEXT, txt);
   ObjectSetString(0, n, OBJPROP_FONT, font);
   ObjectSetInteger(0, n, OBJPROP_FONTSIZE, size);
   ObjectSetInteger(0, n, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, n, OBJPROP_BACK, false);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, n, OBJPROP_HIDDEN, true);
  }

//--- Actualiza el TEXTO/COLOR de una etiqueta de VALOR (objeto "v_<clave>")
void PSet(string nm, string txt, color clr)
  {
   string n = PFX + "v_" + nm;
   ObjectSetString(0, n, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, n, OBJPROP_COLOR, clr);
  }

void PGradient(int x, int y, int w, int h)
  {
   int strip = 6;
   int n = (h + strip - 1) / strip;
   for(int i = 0; i < n; i++)
     {
      double t = (n <= 1) ? 0.0 : (double)i / (n - 1);
      int r = (int)(32 + (12 - 32) * t);
      int g = (int)(36 + (15 - 36) * t);
      int b = (int)(58 + (24 - 58) * t);
      PRect("g" + (string)i, x, y + i * strip, w, strip + 1,
            (color)((b << 16) | (g << 8) | r));
     }
  }

color DDColor(double used, double limit)
  {
   if(limit <= 0.0) return COL_MUT;
   double r = used / limit;
   if(r >= 1.0) return COL_RED;
   if(r >= 0.5) return COL_AMB;
   return COL_GRN;
  }

string g_keys[9] = {"sym","bias","risk","pos","fpnl","trades","realized","balance","equity"};

void CreatePanel()
  {
   if(!InpShowPanel) return;
   int X = InpPanelX, Y = InpPanelY, W = 268, pad = 14, rowH = 25;
   bool prot = InpUseProtection;
   int H = prot ? 441 : 304;

   PGradient(X, Y, W, H);
   PRect("lbar", X, Y, 3, H, InpAccent);
   PRect("tbar", X, Y, W, 4, InpAccent);
   PRect("hsep", X, Y + 54, W, 1, COL_SEP);

   PLabel("title", X + pad, Y + 15, "FOREXBOT", InpAccent, 14, "Arial Black",
          ANCHOR_LEFT_UPPER);
   PLabel("sub", X + pad, Y + 37, StratName(), COL_MUT, 8, "Segoe UI",
          ANCHOR_LEFT_UPPER);

   string caps[9] = {"Simbolo","Senal","Riesgo","Posicion","PnL flotante",
                     "Operaciones","P/L total","Balance","Equity"};
   int y0 = Y + 66;
   for(int i = 0; i < 9; i++)
     {
      int ry = y0 + i * rowH;
      PLabel("c_" + g_keys[i], X + pad, ry, caps[i], COL_MUT, 9, "Segoe UI",
             ANCHOR_LEFT_UPPER);
      PLabel("v_" + g_keys[i], X + W - pad, ry, "—", COL_TXT, 9, "Segoe UI",
             ANCHOR_RIGHT_UPPER);
      if(i < 8)
         PRect("rs" + (string)i, X + pad, ry + rowH - 4, W - 2 * pad, 1, COL_SEP);
     }

   if(prot)
     {
      int yp = y0 + 9 * rowH;
      PRect("psep", X + pad, yp - 2, W - 2 * pad, 1, COL_SEP);
      PLabel("psec", X + pad, yp + 12,
             "PROTECCION  -  margen " + DoubleToString(InpSafetyMarginPct, 1) + "%",
             InpAccent, 8, "Arial Black", ANCHOR_LEFT_UPPER);
      string pcaps[5] = {"Estado","Profit hoy","DD flotante","DD diario","DD total"};
      string pkeys[5] = {"state","dprofit","fdd","ddd","tdd"};
      int yp0 = yp + 32;
      for(int j = 0; j < 5; j++)
        {
         int ry = yp0 + j * rowH;
         PLabel("c_" + pkeys[j], X + pad, ry, pcaps[j], COL_MUT, 9, "Segoe UI",
                ANCHOR_LEFT_UPPER);
         PLabel("v_" + pkeys[j], X + W - pad, ry, "—", COL_TXT, 9, "Segoe UI",
                ANCHOR_RIGHT_UPPER);
         if(j < 4)
            PRect("prs" + (string)j, X + pad, ry + rowH - 4, W - 2 * pad, 1, COL_SEP);
        }
     }
   ChartRedraw();
  }

void UpdatePanel()
  {
   if(!InpShowPanel) return;
   string ccy = AccountInfoString(ACCOUNT_CURRENCY);

   ENUM_SIGNAL bias = CurrentBias();
   string bt = (bias == SIG_LONG) ? "COMPRA" : (bias == SIG_SHORT ? "VENTA" : "NEUTRAL");
   color  bc = (bias == SIG_LONG) ? COL_GRN  : (bias == SIG_SHORT ? COL_RED : COL_MUT);

   string pdesc;
   double fpnl = FloatingPnl(pdesc);
   color  fc = (fpnl > 0) ? COL_GRN : (fpnl < 0 ? COL_RED : COL_TXT);

   int trades; double realized;
   HistoryStats(trades, realized);
   color rc = (realized > 0) ? COL_GRN : (realized < 0 ? COL_RED : COL_TXT);

   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);

   PSet("sym",      _Symbol + "  " + TFString(g_tf), COL_TXT);
   PSet("bias",     bt, bc);
   PSet("risk",     StringFormat("%.2f %%", InpRiskPerTrade * 100.0), COL_TXT);
   PSet("pos",      pdesc, (pdesc == "—") ? COL_MUT : COL_TXT);
   PSet("fpnl",     StringFormat("%.2f %s", fpnl, ccy), fc);
   PSet("trades",   (string)trades, COL_TXT);
   PSet("realized", StringFormat("%.2f %s", realized, ccy), rc);
   PSet("balance",  StringFormat("%.2f %s", bal, ccy), COL_TXT);
   PSet("equity",   StringFormat("%.2f %s", eq, ccy), COL_TXT);

   if(InpUseProtection)
     {
      string st; color sc;
      if(g_haltTotal)       { st = "DETENIDO";    sc = COL_RED; }
      else if(g_targetHit)  { st = "OBJETIVO OK"; sc = COL_GRN; }
      else if(g_haltDaily)  { st = "PAUSA DIA";   sc = COL_AMB; }
      else                  { st = "ACTIVO";      sc = COL_GRN; }

      double keep = 1.0 - InpSafetyMarginPct / 100.0;
      if(keep < 0.0) keep = 0.0;
      double limF = InpMaxFloatDDPct * keep;
      double limD = InpMaxDailyDDPct * keep;
      double limT = InpMaxTotalDDPct * keep;

      PSet("state", st, sc);
      color pcol = (g_dayProfit > 0.0) ? COL_GRN : (g_dayProfit < 0.0 ? COL_RED : COL_TXT);
      if(InpDailyProfitTarget > 0.0)
         PSet("dprofit", StringFormat("%.2f / %.0f %s", g_dayProfit,
                                      InpDailyProfitTarget, ccy), pcol);
      else
         PSet("dprofit", StringFormat("%.2f %s", g_dayProfit, ccy), pcol);
      PSet("fdd", StringFormat("%.2f / %.2f %%", g_floatDDpct, limF),
           DDColor(g_floatDDpct, limF));
      PSet("ddd", StringFormat("%.2f / %.2f %%", g_dailyDDpct, limD),
           DDColor(g_dailyDDpct, limD));
      PSet("tdd", StringFormat("%.2f / %.2f %%", g_totalDDpct, limT),
           DDColor(g_totalDDpct, limT));
     }
   ChartRedraw();
  }

void OnTimer()
  {
   UpdatePanel();
  }

//+------------------------------------------------------------------+
//| OnTick                                                           |
//+------------------------------------------------------------------+
void OnTick()
  {
   bool canTrade = true;
   if(InpUseProtection)
      canTrade = RiskGuard();

   ManageOpenPositions();   // break-even + trailing en cada tick

   // Day trading: cierre de fin de dia (no overnight)
   if(InpCloseEndOfDay && AfterDailyClose())
     {
      CloseAllMyPositions();
      canTrade = false;
     }

   if(InpShowPanel)
      UpdatePanel();

   if(InpNewBarOnly && !IsNewBar())
      return;

   if(!canTrade)
      return;
   if(!InSession())
      return;
   if(CountMyPositions() >= InpMaxPositions)
      return;

   ENUM_SIGNAL sig = GetSignal();
   if(sig == SIG_NONE)
      return;

   OpenTrade(sig);
  }
//+------------------------------------------------------------------+
