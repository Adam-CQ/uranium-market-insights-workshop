import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { AriaComponent, GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";

echarts.use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, AriaComponent, SVGRenderer]);

export function MarketChart({ option, label }: { option: EChartsCoreOption; label: string }) {
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!element.current) return;
    const chart = echarts.init(element.current, undefined, { renderer: "svg" });
    chart.setOption(option);
    const resize = () => chart.resize();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    observer?.observe(element.current);
    window.addEventListener("resize", resize);
    return () => { observer?.disconnect(); window.removeEventListener("resize", resize); chart.dispose(); };
  }, [option]);
  return <div role="img" aria-label={label}><div ref={element} className="market-chart" aria-hidden="true" /></div>;
}
