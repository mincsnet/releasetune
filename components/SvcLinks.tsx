"use client";

import { gaEvent } from "@/components/GoogleAnalytics";
import { SpIcon, ApIcon, AmIcon, YtIcon } from "@/components/Icons";
import type { Track } from "@/lib/utils";

interface SvcLinkProps {
  href: string;
  iconColor: string;
  icon: React.ReactNode;
  label: string;
  large?: boolean;
  trackTitle?: string;
  artist?: string;
}

export function SvcLink({ href, iconColor, icon, label, large, trackTitle, artist }: SvcLinkProps) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onClick={() =>
        gaEvent("click_streaming", {
          service: label,
          track_title: trackTitle ?? "",
          artist: artist ?? "",
        })
      }
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontSize: large ? "0.8rem" : "0.68rem",
        padding: large ? "9px 14px" : "4px 10px",
        borderRadius: 4,
        border: "1px solid var(--border)",
        color: "var(--text-sec)",
        textDecoration: "none",
        background: "transparent",
        fontWeight: 500,
        whiteSpace: "nowrap",
        transition: "background 0.15s, border-color 0.15s",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLAnchorElement).style.background = "var(--surface2)";
        (e.currentTarget as HTMLAnchorElement).style.borderColor = "#555";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLAnchorElement).style.background = "transparent";
        (e.currentTarget as HTMLAnchorElement).style.borderColor = "var(--border)";
      }}
    >
      <span style={{ color: iconColor, display: "flex", alignItems: "center" }}>{icon}</span>
      {label}
    </a>
  );
}

interface SvcGridProps {
  links?: Track["links"];
  trackTitle?: string;
  artist?: string;
}

export function SvcGrid({ links, trackTitle, artist }: SvcGridProps) {
  const youtubeMusicHref = links?.youtubeId
    ? `https://music.youtube.com/watch?v=${links.youtubeId}`
    : links?.youtube;

  const items = [
    links?.spotify && {
      href: links.spotify,
      iconColor: "#1DB954",
      icon: <SpIcon s={14} />,
      label: "Spotify",
    },
    links?.apple && {
      href: links.apple,
      iconColor: "#fc3c44",
      icon: <ApIcon s={14} />,
      label: "Apple Music",
    },
    links?.amazon && {
      href: links.amazon,
      iconColor: "#00A8E1",
      icon: <AmIcon s={14} />,
      label: "Amazon Music",
    },
    youtubeMusicHref && {
      href: youtubeMusicHref,
      iconColor: "#FF0000",
      icon: <YtIcon s={14} />,
      label: "YouTube Music",
    },
  ].filter(Boolean) as SvcLinkProps[];

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 8,
      }}
    >
      {items.map((item) => (
        <SvcLink key={item.label} {...item} large trackTitle={trackTitle} artist={artist} />
      ))}
    </div>
  );
}

interface TrackSvcLinksProps {
  links?: Track["links"];
  trackTitle?: string;
  artist?: string;
}

export function TrackSvcLinks({ links, trackTitle, artist }: TrackSvcLinksProps) {
  const youtubeMusicHref = links?.youtubeId
    ? `https://music.youtube.com/watch?v=${links.youtubeId}`
    : links?.youtube;

  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {links?.spotify && (
        <SvcLink
          href={links.spotify}
          iconColor="#1DB954"
          icon={<SpIcon />}
          label="Spotify"
          trackTitle={trackTitle}
          artist={artist}
        />
      )}
      {links?.apple && (
        <SvcLink
          href={links.apple}
          iconColor="#fc3c44"
          icon={<ApIcon />}
          label="Apple Music"
          trackTitle={trackTitle}
          artist={artist}
        />
      )}
      {links?.amazon && (
        <SvcLink
          href={links.amazon}
          iconColor="#00A8E1"
          icon={<AmIcon />}
          label="Amazon Music"
          trackTitle={trackTitle}
          artist={artist}
        />
      )}
      {youtubeMusicHref && (
        <SvcLink
          href={youtubeMusicHref}
          iconColor="#FF0000"
          icon={<YtIcon />}
          label="YouTube Music"
          trackTitle={trackTitle}
          artist={artist}
        />
      )}
    </div>
  );
}
