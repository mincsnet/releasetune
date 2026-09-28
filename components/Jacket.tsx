"use client";

import { useState } from "react";
import Image from "next/image";

interface JacketProps {
  jacket?: string;
  title: string;
  size?: number;
  fullWidth?: boolean;
}

export function Jacket({ jacket, title, size = 68, fullWidth = false }: JacketProps) {
  const [err, setErr] = useState(false);
  // 親のCSSで --jacket-size を指定すると size より優先される（画面幅ごとの切り替え用）
  const box = `var(--jacket-size, ${size}px)`;

  const containerStyle = fullWidth
    ? {
        width: "100%",
        aspectRatio: "1/1" as const,
        position: "relative" as const,
        borderRadius: 4,
        overflow: "hidden",
        background: "linear-gradient(135deg, #c8a84b33 0%, #1e1e1e 100%)",
      }
    : {
        width: box,
        height: box,
        flexShrink: 0,
        borderRadius: 4,
        overflow: "hidden",
        position: "relative" as const,
      };

  if (!jacket || err) {
    return (
      <div
        style={{
          ...containerStyle,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: fullWidth ? "4rem" : `calc(${box} * 0.3)`,
          color: "#c8a84bcc",
        }}
      >
        ♪
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <Image
        src={jacket}
        alt={title}
        fill
        sizes={fullWidth ? "100vw" : `${size}px`}
        style={{ objectFit: "cover" }}
        onError={() => setErr(true)}
        unoptimized
      />
    </div>
  );
}
