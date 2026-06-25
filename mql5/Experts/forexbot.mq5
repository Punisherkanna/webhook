//+------------------------------------------------------------------+
//|                                                     forexbot.mq5  |
//|   Robot de trading Forex - tendencia/momentum de una sola        |
//|   posicion con stops basados en ATR.                             |
//|   SIN grid / hedging / HFT / martingala.                         |
//|                                                                  |
//|   Portado del bot Python del mismo repositorio. Mismas 5         |
//|   estrategias seleccionables por parametro.                      |
//+------------------------------------------------------------------+
#property copyright "forexbot"
#property link      "https://github.com/Punisherkanna/webhook"
#property version   "1.00"
#property description "Forex EA: MA crossover, RSI, Donchian, MACD, Bollinger."
#property strict

#include <Trade/Trade.mqh>

//--- Estrategia seleccionable
enum ENUM_STRATEGY
  {
   STRAT_MA_CROSSOVER,        // MA crossover (cruce de medias)
   STRAT_RSI_REVERSION,       // RSI reversion (reversion)
   STRAT_DONCHIAN_BREAKOUT,   // Donchian breakout (ruptura de canal)
   STRAT_MACD_TREND,          // MACD trend (tendencia con filtro EMA)
   STRAT_BOLLINGER_BREAKOUT   // Bollinger breakout (ruptura de banda)
  };

enum ENUM_SIGNAL { SIG_NONE, SIG_LONG, SIG_SHORT };

//============================ Parametros ============================
input group "General"
input ENUM_STRATEGY   InpStrategy        = STRAT_MA_CROSSOVER; // Estrategia
input ENUM_TIMEFRAMES InpTimeframe       = PERIOD_CURRENT;     // Temporalidad
input long            InpMagic           = 234000;             // Numero magico
input bool            InpNewBarOnly       = true;              // Operar solo en vela cerrada
input ulong           InpDeviation       = 20;                 // Desviacion maxima (puntos)
input string          InpComment         = "forexbot";         // Comentario de orden

input group "Riesgo / dimensionamiento"
input double InpRiskPerTrade   = 0.01;  // Riesgo por operacion (fraccion de equity, 0-1)
input double InpMaxLots        = 10.0;  // Lote maximo permitido
input int    InpMaxPositions   = 1;     // Maximo de posiciones simultaneas (de este EA)

input group "Stops por ATR"
input int    InpAtrPeriod = 14;   // Periodo ATR
input double InpAtrStop    = 2.0; // Stop = ATR * este factor
input double InpAtrTarget  = 3.0; // Objetivo = ATR * este factor

input group "MA crossover"
input int InpMaFast = 10;   // SMA rapida
input int InpMaSlow = 30;   // SMA lenta

input group "RSI reversion"
input int    InpRsiPeriod     = 14; // Periodo RSI
input double InpRsiOversold   = 30; // Nivel de sobreventa
input double InpRsiOverbought = 70; // Nivel de sobrecompra

input group "Donchian breakout"
input int InpDonchianPeriod = 20;   // Periodo del canal (velas previas)

input group "MACD trend"
input int InpMacdFast        = 12;  // EMA rapida MACD
input int InpMacdSlow        = 26;  // EMA lenta MACD
input int InpMacdSignal      = 9;   // EMA de la senal MACD
input int InpMacdTrendPeriod = 100; // EMA del filtro de tendencia

input group "Bollinger breakout"
input int    InpBbPeriod = 20;  // Periodo de las bandas
input double InpBbStd    = 2.0; // Desviaciones estandar

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
#define COL_SEP C'46,49,68'

//============================ Estado global ========================
CTrade        g_trade;
ENUM_TIMEFRAMES g_tf;
datetime      g_lastBar = 0;

int h_atr   = INVALID_HANDLE;
int h_fast  = INVALID_HANDLE;
int h_slow  = INVALID_HANDLE;
int h_rsi   = INVALID_HANDLE;
int h_macd  = INVALID_HANDLE;
int h_trend = INVALID_HANDLE;
int h_bands = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Utilidad: leer un valor de un buffer de indicador (serie)        |
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
//| OnInit: validar parametros y crear los handles necesarios        |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_tf = (InpTimeframe == PERIOD_CURRENT) ? (ENUM_TIMEFRAMES)Period() : InpTimeframe;

   if(InpRiskPerTrade <= 0.0 || InpRiskPerTrade > 1.0)
     {
      Print("ERROR: InpRiskPerTrade debe estar en (0, 1]");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpStrategy == STRAT_MA_CROSSOVER && InpMaFast >= InpMaSlow)
     {
      Print("ERROR: la SMA rapida debe ser menor que la lenta");
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

   switch(InpStrategy)
     {
      case STRAT_MA_CROSSOVER:
         h_fast = iMA(_Symbol, g_tf, InpMaFast, 0, MODE_SMA, PRICE_CLOSE);
         h_slow = iMA(_Symbol, g_tf, InpMaSlow, 0, MODE_SMA, PRICE_CLOSE);
         break;
      case STRAT_RSI_REVERSION:
         h_rsi = iRSI(_Symbol, g_tf, InpRsiPeriod, PRICE_CLOSE);
         break;
      case STRAT_DONCHIAN_BREAKOUT:
         break; // usa iHighest/iLowest, sin handle
      case STRAT_MACD_TREND:
         h_macd  = iMACD(_Symbol, g_tf, InpMacdFast, InpMacdSlow, InpMacdSignal, PRICE_CLOSE);
         h_trend = iMA(_Symbol, g_tf, InpMacdTrendPeriod, 0, MODE_EMA, PRICE_CLOSE);
         break;
      case STRAT_BOLLINGER_BREAKOUT:
         h_bands = iBands(_Symbol, g_tf, InpBbPeriod, 0, InpBbStd, PRICE_CLOSE);
         break;
     }

   if(h_atr == INVALID_HANDLE)
     {
      Print("ERROR: no se pudo crear el handle de ATR");
      return INIT_FAILED;
     }
   // Verificar que los handles de la estrategia elegida existen
   if((InpStrategy == STRAT_MA_CROSSOVER && (h_fast == INVALID_HANDLE || h_slow == INVALID_HANDLE)) ||
      (InpStrategy == STRAT_RSI_REVERSION && h_rsi == INVALID_HANDLE) ||
      (InpStrategy == STRAT_MACD_TREND && (h_macd == INVALID_HANDLE || h_trend == INVALID_HANDLE)) ||
      (InpStrategy == STRAT_BOLLINGER_BREAKOUT && h_bands == INVALID_HANDLE))
     {
      Print("ERROR: no se pudieron crear los indicadores de la estrategia");
      return INIT_FAILED;
     }

   PrintFormat("forexbot iniciado: estrategia=%d  simbolo=%s  TF=%d",
               InpStrategy, _Symbol, g_tf);

   CreatePanel();
   UpdatePanel();
   if(InpShowPanel)
      EventSetTimer(1);          // refresco del PnL flotante cada segundo

   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| OnDeinit: liberar handles                                        |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   int handles[] = {h_atr, h_fast, h_slow, h_rsi, h_macd, h_trend, h_bands};
   for(int i = 0; i < ArraySize(handles); i++)
      if(handles[i] != INVALID_HANDLE)
         IndicatorRelease(handles[i]);

   EventKillTimer();
   ObjectsDeleteAll(0, PFX);
   ChartRedraw();
  }

//+------------------------------------------------------------------+
//| Deteccion de vela nueva                                          |
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

//+------------------------------------------------------------------+
//| Numero de posiciones de este EA en este simbolo                  |
//+------------------------------------------------------------------+
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

//+------------------------------------------------------------------+
//| Senales por estrategia (evaluadas en la vela cerrada, shift 1/2) |
//+------------------------------------------------------------------+
ENUM_SIGNAL SignalMA()
  {
   double f1 = IndVal(h_fast, 0, 1), f2 = IndVal(h_fast, 0, 2);
   double s1 = IndVal(h_slow, 0, 1), s2 = IndVal(h_slow, 0, 2);
   if(!Valid(f1) || !Valid(f2) || !Valid(s1) || !Valid(s2))
      return SIG_NONE;
   if(f2 <= s2 && f1 > s1) return SIG_LONG;
   if(f2 >= s2 && f1 < s1) return SIG_SHORT;
   return SIG_NONE;
  }

ENUM_SIGNAL SignalRSI()
  {
   double r1 = IndVal(h_rsi, 0, 1), r2 = IndVal(h_rsi, 0, 2);
   if(!Valid(r1) || !Valid(r2))
      return SIG_NONE;
   if(r2 <= InpRsiOversold   && r1 > InpRsiOversold)   return SIG_LONG;
   if(r2 >= InpRsiOverbought && r1 < InpRsiOverbought) return SIG_SHORT;
   return SIG_NONE;
  }

ENUM_SIGNAL SignalDonchian()
  {
   int bars = Bars(_Symbol, g_tf);
   if(bars < InpDonchianPeriod + 3)
      return SIG_NONE;
   // Canal de las N velas previas a la vela cerrada (shift 2..N+1).
   int idxH = iHighest(_Symbol, g_tf, MODE_HIGH, InpDonchianPeriod, 2);
   int idxL = iLowest(_Symbol, g_tf, MODE_LOW,  InpDonchianPeriod, 2);
   if(idxH < 0 || idxL < 0)
      return SIG_NONE;
   double upper = iHigh(_Symbol, g_tf, idxH);
   double lower = iLow(_Symbol, g_tf, idxL);
   double high1 = iHigh(_Symbol, g_tf, 1);
   double low1  = iLow(_Symbol, g_tf, 1);
   if(high1 > upper) return SIG_LONG;
   if(low1  < lower) return SIG_SHORT;
   return SIG_NONE;
  }

ENUM_SIGNAL SignalMACD()
  {
   double m1 = IndVal(h_macd, 0, 1), m2 = IndVal(h_macd, 0, 2); // MAIN
   double g1 = IndVal(h_macd, 1, 1), g2 = IndVal(h_macd, 1, 2); // SIGNAL
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

ENUM_SIGNAL SignalBollinger()
  {
   double u1 = IndVal(h_bands, 1, 1), u2 = IndVal(h_bands, 1, 2); // UPPER
   double l1 = IndVal(h_bands, 2, 1), l2 = IndVal(h_bands, 2, 2); // LOWER
   if(!Valid(u1) || !Valid(u2) || !Valid(l1) || !Valid(l2))
      return SIG_NONE;
   double c1 = iClose(_Symbol, g_tf, 1), c2 = iClose(_Symbol, g_tf, 2);
   if(c2 <= u2 && c1 > u1) return SIG_LONG;
   if(c2 >= l2 && c1 < l1) return SIG_SHORT;
   return SIG_NONE;
  }

ENUM_SIGNAL GetSignal()
  {
   switch(InpStrategy)
     {
      case STRAT_MA_CROSSOVER:      return SignalMA();
      case STRAT_RSI_REVERSION:     return SignalRSI();
      case STRAT_DONCHIAN_BREAKOUT: return SignalDonchian();
      case STRAT_MACD_TREND:        return SignalMACD();
      case STRAT_BOLLINGER_BREAKOUT:return SignalBollinger();
     }
   return SIG_NONE;
  }

//+------------------------------------------------------------------+
//| Dimensionamiento por riesgo (usa tick value real del simbolo)    |
//+------------------------------------------------------------------+
int VolumeDigits(double step)
  {
   int d = 0;
   while(step < 1.0 && d < 8)
     {
      step *= 10.0;
      d++;
     }
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

   double moneyPerLot = (stopDistance / tickSize) * tickValue; // perdida por 1 lote al stop
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

   lots = MathFloor(lots / step) * step;          // redondeo conservador hacia abajo
   if(lots < minLot)
      return 0.0;                                  // demasiado pequeno: no operar
   if(lots > maxLot)
      lots = maxLot;
   return NormalizeDouble(lots, VolumeDigits(step));
  }

//+------------------------------------------------------------------+
//| Abrir una operacion con SL/TP basados en ATR                     |
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

   double price, sl, tp;
   double stopDist = atr * InpAtrStop;
   double tgtDist  = atr * InpAtrTarget;
   if(stopDist < minDist) stopDist = minDist;     // respetar distancia minima del broker
   if(tgtDist  < minDist) tgtDist  = minDist;

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

//============================ Panel visual =========================
string StratName()
  {
   switch(InpStrategy)
     {
      case STRAT_MA_CROSSOVER:       return "MA Crossover";
      case STRAT_RSI_REVERSION:      return "RSI Reversion";
      case STRAT_DONCHIAN_BREAKOUT:  return "Donchian Breakout";
      case STRAT_MACD_TREND:         return "MACD Trend";
      case STRAT_BOLLINGER_BREAKOUT: return "Bollinger Breakout";
     }
   return "—";
  }

string TFString(ENUM_TIMEFRAMES tf)
  {
   string s = EnumToString(tf);
   StringReplace(s, "PERIOD_", "");
   return s;
  }

//--- "Bias" direccional actual (estado de los indicadores, no el cruce)
ENUM_SIGNAL CurrentBias()
  {
   switch(InpStrategy)
     {
      case STRAT_MA_CROSSOVER:
        {
         double f = IndVal(h_fast, 0, 1), s = IndVal(h_slow, 0, 1);
         if(!Valid(f) || !Valid(s)) return SIG_NONE;
         return (f > s) ? SIG_LONG : SIG_SHORT;
        }
      case STRAT_RSI_REVERSION:
        {
         double r = IndVal(h_rsi, 0, 1);
         if(!Valid(r)) return SIG_NONE;
         if(r < InpRsiOversold)   return SIG_LONG;
         if(r > InpRsiOverbought) return SIG_SHORT;
         return SIG_NONE;
        }
      case STRAT_DONCHIAN_BREAKOUT:
        {
         int ih = iHighest(_Symbol, g_tf, MODE_HIGH, InpDonchianPeriod, 1);
         int il = iLowest(_Symbol, g_tf, MODE_LOW, InpDonchianPeriod, 1);
         if(ih < 0 || il < 0) return SIG_NONE;
         double up = iHigh(_Symbol, g_tf, ih), lo = iLow(_Symbol, g_tf, il);
         double c = iClose(_Symbol, g_tf, 1);
         return (c >= (up + lo) / 2.0) ? SIG_LONG : SIG_SHORT;
        }
      case STRAT_MACD_TREND:
        {
         double m = IndVal(h_macd, 0, 1), g = IndVal(h_macd, 1, 1);
         double tr = IndVal(h_trend, 0, 1);
         if(!Valid(m) || !Valid(g) || !Valid(tr)) return SIG_NONE;
         double c = iClose(_Symbol, g_tf, 1);
         if(m > g && c > tr) return SIG_LONG;
         if(m < g && c < tr) return SIG_SHORT;
         return SIG_NONE;
        }
      case STRAT_BOLLINGER_BREAKOUT:
        {
         double u = IndVal(h_bands, 1, 1), l = IndVal(h_bands, 2, 1);
         if(!Valid(u) || !Valid(l)) return SIG_NONE;
         double c = iClose(_Symbol, g_tf, 1);
         if(c > u) return SIG_LONG;
         if(c < l) return SIG_SHORT;
         return SIG_NONE;
        }
     }
   return SIG_NONE;
  }

//--- PnL flotante de este EA + descripcion de la posicion abierta
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

//--- Operaciones cerradas y P/L realizado total de este EA
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

//--- Helpers de objetos graficos -----------------------------------
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

void PSet(string nm, string txt, color clr)
  {
   string n = PFX + nm;
   ObjectSetString(0, n, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, n, OBJPROP_COLOR, clr);
  }

//--- Fondo con degradado vertical (simula una imagen, sin archivos)
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

string g_keys[9] = {"sym","bias","risk","pos","fpnl","trades","realized","balance","equity"};

void CreatePanel()
  {
   if(!InpShowPanel) return;
   int X = InpPanelX, Y = InpPanelY, W = 268, pad = 14, H = 304;

   PGradient(X, Y, W, H);
   PRect("lbar", X, Y, 3, H, InpAccent);          // barra de acento izquierda
   PRect("tbar", X, Y, W, 4, InpAccent);          // barra de acento superior
   PRect("hsep", X, Y + 54, W, 1, COL_SEP);       // separador de cabecera

   PLabel("title", X + pad, Y + 15, "FOREXBOT", InpAccent, 14, "Arial Black",
          ANCHOR_LEFT_UPPER);
   PLabel("sub", X + pad, Y + 37, StratName(), COL_MUT, 8, "Segoe UI",
          ANCHOR_LEFT_UPPER);

   string caps[9] = {"Simbolo","Senal","Riesgo","Posicion","PnL flotante",
                     "Operaciones","P/L total","Balance","Equity"};
   int y0 = Y + 66, rowH = 25;
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
   if(InpShowPanel)
      UpdatePanel();              // refresco en vivo en cada tick

   if(InpNewBarOnly && !IsNewBar())
      return;

   if(CountMyPositions() >= InpMaxPositions)
      return;                                      // ya hay una posicion abierta

   ENUM_SIGNAL sig = GetSignal();
   if(sig == SIG_NONE)
      return;

   OpenTrade(sig);
  }
//+------------------------------------------------------------------+
