


pub struct RingBuffer<const N: usize> {
    buffer: [u16; N],
    head: u8,
    sum: u16,
    count: u8,
}

impl<const N: usize> RingBuffer<N> {
    #[inline(always)]
    pub const fn new() -> Self {
        Self {
            //buffer: unsafe { MaybeUninit::uninit().assume_init() },
            buffer: [0; N],
            head: 0,
            sum: 0,
            count: 0,
        }
    }

    #[inline(always)]
    pub fn push(&mut self, value: u16) {
        if (self.count as usize) < N {
            // Buffer not full yet
            self.buffer[self.head as usize] = value;
            self.sum = self.sum + value;
            self.count += 1;
        } else {
            // Buffer is full, replace oldest value
            let old_value = self.buffer[self.head as usize];
            self.buffer[self.head as usize] = value;
            self.sum = self.sum - old_value + value;
        }
        
        // Advance head pointer with wraparound
        self.head = ((self.head + 1) as usize % N) as u8;
    }

    #[inline(always)]
    pub fn average(&self) -> Option<u16> {
        if self.count == 0 {
            None
        } else {
            Some(self.sum / self.count as u16)
        }
    }

    #[inline(always)]
    pub fn sum(&self) -> u16 {
        self.sum
    }

    #[inline(always)]
    pub fn len(&self) -> u8 {
        self.count
    }

    #[inline(always)]
    pub fn is_full(&self) -> bool {
        self.count as usize == N
    }

    #[inline(always)]
    pub fn is_empty(&self) -> bool {
        self.count == 0
    }

    #[inline(always)]
    pub fn clear(&mut self) {
        self.head = 0;
        self.count = 0;
        self.sum = 0;
        // Note: We don't need to clear the buffer array since we track count
    }

    pub fn all_same(&self)->bool{
        if (self.count as usize) < N {
            false
        }else{
            let first = self.buffer[0];
            for i in &self.buffer[1..]{
                if *i != first{
                    return false
                }
            }
            true
        }
    }
}
