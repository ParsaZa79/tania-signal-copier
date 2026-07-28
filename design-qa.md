# New order workspace design QA

- Source visual truth: `/Users/parsaz/.codex/generated_images/019faad3-b071-73d2-bdfa-2a4ddcf13e63/call_dLu4Y11W49CjxpIhKoyq7mU6.png`
- Implementation screenshot: `/tmp/signal-copier-tradingview-advanced-final-v3.png`
- Combined comparison: `/tmp/signal-copier-orders-comparison-tradingview.png`
- Requested viewport: 1440 x 1024 CSS px
- Captured viewport: 1434 x 1020 px after the in-app browser frame inset
- Source pixels: 1487 x 1058, normalized to 1434 x 1020 for comparison
- Implementation pixels: 1434 x 1020
- Device scale/density normalization: both comparison halves are 1434 x 1020 at 1:1 density
- State: authenticated dark desktop order route, XAUUSDb, Buy, Market, 0.01 lots, official TradingView Advanced Chart at 15 minutes

## Full-view comparison evidence

The final comparison places the selected first direction and the implementation side by side at the same pixel dimensions. Both preserve the existing dashboard shell while presenting the same two-column guided-order composition: numbered progress rail, instrument selector, paired direction and order-type controls, compact lot stepper, optional risk controls, order summary, blue review CTA, live quote header, candle chart, day range, and nearby-markets table.

The implementation intentionally uses the product's existing typography, color tokens, symbol icons, sidebar, header, and live-account chrome. At the user's request, the compact chart from the selected concept has been replaced with TradingView's official Advanced Chart experience, so the right column is taller and scrolls to reveal the remaining market rows. Quote values and candle shapes differ because market data is time-sensitive and the chart uses TradingView's mapped venue.

## Focused-region evidence

No additional crop was required because the equal-size full-view comparison keeps both primary fidelity regions readable:

- Left: the entire guided order ticket, including the complete primary CTA.
- Right: live quote, TradingView top and drawing toolbars, candlestick plot, volume, date ranges, attribution, range indicator, and market table.

## Required fidelity surfaces

- Fonts and typography: existing dashboard font family and weights are retained; heading, label, numeric, and helper-text hierarchy closely follows the selected direction.
- Spacing and layout rhythm: the 1.12 / 0.88 desktop split, 20 px section rhythm, compact 44 px controls, 64 px instrument card, and 390 px chart preserve the ticket while giving TradingView's toolbars enough usable space.
- Colors and visual tokens: existing near-black surfaces, subtle borders, blue selection states, blue CTA, and green/red market semantics are preserved.
- Image and icon fidelity: existing real flag, commodity, crypto, and Lucide assets are used. The chart is TradingView's official Advanced Chart widget with its native icons, toolbars, and attribution.
- Copy and content: user-facing language follows the chosen direction and uses live broker labels and quote data.
- Live data: the bid, ask, spread, day range, and nearby markets remain connected to MT5. The embedded chart maps broker symbols to suitable TradingView venues, including OANDA for FX/metals and Bitstamp for BTCUSD.

## Comparison history

### Iteration 1 — blocked

- Finding: P2 right column was too wide, the 250 px chart pushed the lower market rows out of view, risk controls lacked the selected direction's steppers, and the nearby-markets change column was missing.
- Fix: adjusted the desktop grid proportions, added stop-loss and take-profit steppers, added the change column and four-row market table, and introduced the live chart component.

### Iteration 2 — blocked

- Finding: P2 vertical density left the review CTA touching the lower viewport edge; the instrument change label truncated; an unsuffixed BTCUSD quote produced repeated console errors.
- Fix: reduced section gaps and core control heights, widened the market selector, preserved BTCUSD without a broker suffix, and reduced the chart to 220 px.

### Iteration 3 — passed

- Visual evidence: the final equal-size comparison shows the complete ticket and market context without clipping or overflow.
- Interaction checks: Buy/Sell, Market/Pending, pending type and entry price, volume stepper, timeframe selection, nearby-market switching, and the review dialog all worked. The final placement action was intentionally not invoked because it would send a real broker order.
- Responsive check: the core order controls and review CTA remain present at 390 x 844; the existing mobile navigation is retained.
- Browser diagnostics: no application console errors remained after the BTCUSD compatibility fix.

### Iteration 4 — passed

- User feedback: the compact TradingView rendering engine did not look like TradingView's own platform.
- Fix: replaced the custom Lightweight Charts presentation with the official TradingView Advanced Chart widget, including interval and candle controls, indicators, drawing tools, crosshair, volume, date ranges, UTC clock, and required attribution.
- Functional evidence: XAUUSDb maps to `OANDA:XAUUSD`, EURUSDb maps to `OANDA:EURUSD`, nearby-market selection remounts the correct chart, and the 1-hour / 15-minute interval controls update inside the embedded widget.
- Browser diagnostics: the application itself remained error-free. TradingView's embedded support-portal request returned a non-blocking 403 while the chart and controls continued to work.
- Automated checks: dashboard lint, 37 dashboard tests, dashboard production build, 85 API tests with 36 skipped, and `git diff --check` passed.

## Findings

No actionable P0, P1, or P2 visual or interaction differences remain for the selected direction.

final result: passed
