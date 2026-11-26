'use client';

import React from 'react';

export default function QueueStorageHeader() {
  return (
    <div className="space-y-1">
      <h1 className="text-2xl font-semibold leading-8 tracking-tight text-[#141b2c] dark:text-foreground">
        Hàng đợi & Lưu trữ
      </h1>
      <p className="max-w-2xl text-sm leading-5 text-[#5c4039] dark:text-muted-foreground">
        Giám sát tiến trình phân tích nền không đồng bộ và quản lý dung lượng lưu trữ hệ thống.
      </p>
    </div>
  );
}
