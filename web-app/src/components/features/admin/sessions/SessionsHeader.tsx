'use client';

import React from 'react';

export default function SessionsHeader() {
  return (
    <div className="space-y-1">
      <h1 className="text-2xl font-semibold leading-8 tracking-tight text-[#141b2c] dark:text-foreground">
        Giám sát phiên phỏng vấn
      </h1>
      <p className="max-w-2xl text-sm leading-5 text-[#5c4039] dark:text-muted-foreground">
        Tra cứu các phiên phỏng vấn và xem nội dung hỏi đáp, bằng chứng, kết quả sau khi phiên kết thúc.
      </p>
    </div>
  );
}
