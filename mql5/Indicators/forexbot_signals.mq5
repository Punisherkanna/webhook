//+------------------------------------------------------------------+
//|                                            forexbot_signals.mq5   |
//|   Indicador grafico companero del EA forexbot.                   |
//|   Dibuja en el grafico las senales de las dos estrategias del    |
//|   EA (flechas de compra/venta) y, opcionalmente, el canal        |
//|   Donchian. Sirve para VER donde entraria el robot.              |
//+------------------------------------------------------------------+
#property copyright "forexbot"
#property link      "https://github.com/Punisherkanna/webhook"
#property version   "1.00"
#property description "Senales de forexbot: Donchian breakout / MACD trend."
#property indicator_chart_window
#property indicator_buffers 4
#property indicator_plots   3

//--- Plot: flecha de compra
#property indicator_label1  "Compra"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrLimeGreen
#property indicator_width1  2
//--- Plot: flecha de venta
#property indicator_label2  "Venta"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrTomato
#property indicator_width2  2
//--- Plot: canal Donchian (dos lineas en un mismo plot tipo channel)
#property indicator_label3  "Canal Donchian"
#property indicator_type3   DRAW_FILLING
#property indicator_color3  clrSlateGray

enum ENUM_IND_STRATEGY
  {
   IND_DONCHIAN,   // Donchian breakout
   IND_MACD        // MACD trend
  };

input ENUM_IND_STRATEGY InpStrategy   = IND_DONCHIAN; // Estrategia a marcar
input bool              InpShowChannel = true;        // Mostrar canal Donchian
input int  InpDonchianPeriod = 20;   // Periodo del canal
input int  InpMacdFast       = 12;   // EMA rapida MACD
input int  InpMacdSlow       = 26;   // EMA lenta MACD
input int  InpMacdSignal     = 9;    // EMA de la senal MACD
input int  InpMacdTrendPeriod = 100; // EMA del filtro de tendencia
input double InpArrowOffset   = 0.6; // Separacion de la flecha (en ATR(14))

double BufBuy[];
double BufSell[];
double BufUpper[];
double BufLower[];

int h_macd  = INVALID_HANDLE;
int h_trend = INVALID_HANDLE;
int h_atr   = INVALID_HANDLE;

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, BufBuy,   INDICATOR_DATA);
   SetIndexBuffer(1, BufSell,  INDICATOR_DATA);
   SetIndexBuffer(2, BufUpper, INDICATOR_DATA);
   SetIndexBuffer(3, BufLower, INDICATOR_DATA);

   PlotIndexSetInteger(0, PLOT_ARROW, 233);   // flecha arriba
   PlotIndexSetInteger(1, PLOT_ARROW, 234);   // flecha abajo
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, 0.0);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, 0.0);

   if(!InpShowChannel)
     {
      PlotIndexSetInteger(2, PLOT_DRAW_TYPE, DRAW_NONE);
     }

   h_atr = iATR(_Symbol, _Period, 14);
   if(InpStrategy == IND_MACD)
     {
      h_macd  = iMACD(_Symbol, _Period, InpMacdFast, InpMacdSlow, InpMacdSignal, PRICE_CLOSE);
      h_trend = iMA(_Symbol, _Period, InpMacdTrendPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(h_macd == INVALID_HANDLE || h_trend == INVALID_HANDLE)
         return INIT_FAILED;
     }
   if(h_atr == INVALID_HANDLE)
      return INIT_FAILED;

   IndicatorSetString(INDICATOR_SHORTNAME, "forexbot signals");
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(h_macd  != INVALID_HANDLE) IndicatorRelease(h_macd);
   if(h_trend != INVALID_HANDLE) IndicatorRelease(h_trend);
   if(h_atr   != INVALID_HANDLE) IndicatorRelease(h_atr);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   int need = MathMax(InpDonchianPeriod + 2, InpMacdSlow + InpMacdSignal + 2);
   if(rates_total < need + 2)
      return 0;

   // ATR para separar las flechas del precio.
   double atr[];
   ArraySetAsSeries(atr, false);
   if(CopyBuffer(h_atr, 0, 0, rates_total, atr) < rates_total)
      return prev_calculated;

   double macd[], sig[], ema[];
   if(InpStrategy == IND_MACD)
     {
      ArraySetAsSeries(macd, false); ArraySetAsSeries(sig, false); ArraySetAsSeries(ema, false);
      if(CopyBuffer(h_macd, 0, 0, rates_total, macd) < rates_total) return prev_calculated;
      if(CopyBuffer(h_macd, 1, 0, rates_total, sig)  < rates_total) return prev_calculated;
      if(CopyBuffer(h_trend, 0, 0, rates_total, ema) < rates_total) return prev_calculated;
     }

   int start = (prev_calculated > 1) ? prev_calculated - 1 : need;
   for(int i = start; i < rates_total; i++)
     {
      BufBuy[i]  = 0.0;
      BufSell[i] = 0.0;
      BufUpper[i] = EMPTY_VALUE;
      BufLower[i] = EMPTY_VALUE;
      if(i < need) continue;

      double a = (atr[i] > 0 ? atr[i] : (close[i] * 0.001));
      double off = a * InpArrowOffset;

      // Canal Donchian de las 'period' velas previas (i-period .. i-1)
      double upper = high[i - 1], lower = low[i - 1];
      for(int k = 2; k <= InpDonchianPeriod; k++)
        {
         upper = MathMax(upper, high[i - k]);
         lower = MathMin(lower, low[i - k]);
        }
      if(InpShowChannel)
        {
         BufUpper[i] = upper;
         BufLower[i] = lower;
        }

      bool buy = false, sell = false;
      if(InpStrategy == IND_DONCHIAN)
        {
         if(high[i] > upper) buy = true;
         if(low[i]  < lower) sell = true;
        }
      else // MACD trend
        {
         bool up   = (macd[i - 1] <= sig[i - 1] && macd[i] > sig[i]);
         bool down = (macd[i - 1] >= sig[i - 1] && macd[i] < sig[i]);
         if(up   && close[i] > ema[i]) buy = true;
         if(down && close[i] < ema[i]) sell = true;
        }

      if(buy)  BufBuy[i]  = low[i]  - off;
      if(sell) BufSell[i] = high[i] + off;
     }
   return rates_total;
  }
//+------------------------------------------------------------------+
