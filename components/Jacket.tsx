"use client";

import { useState } from "react";
import Image from "next/image";

interface JacketProps {
  jacket?: string;
  title: string;
  size?: number;
}

export function Jacket({ jacket, title, size = 68 }: JacketProps) {
  const [err, setErr] = useState(false);

  if (!jacket || err) {
    return (
      <div
        style={{
          width: size,
          height: size,
          flexShrink: 0,
          borderRadius: 4,
          background: "linear-gradient(135deg, #c8a84b33 0%, #1e1e1e 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: size * 0.3,
          color: "#c8a84bcc",
        }}
      >
        ♪
      </div>
    );
  }

  return (
    <div
      style={{
        width: size,
        height: size,
        flexShrink: 0,
        borderRadius: 4,
        overflow: "hidden",
        position: "relative",
      }}
    >
      <Image
        src={jacket}
        alt={title}
        fill
        sizes={`${size}px`}
        style={{ objectFit: "cover" }}
        onError={() => setErr(true)}
        unoptimized
      />
    </div>
  );
}
