import AVFoundation
import Foundation

// usage: record_window.swift <out.mov> <x> <y> <w> <h> <seconds> [fps]
let a = CommandLine.arguments
guard a.count >= 7, let x = Double(a[2]), let y = Double(a[3]),
      let w = Double(a[4]), let h = Double(a[5]), let secs = Double(a[6]) else {
    fputs("usage: record_window out x y w h seconds [fps]\n", stderr)
    exit(2)
}
let fps = a.count > 7 ? (Double(a[7]) ?? 15) : 15

let out = URL(fileURLWithPath: a[1])
try? FileManager.default.removeItem(at: out)
try FileManager.default.createDirectory(at: out.deletingLastPathComponent(),
                                        withIntermediateDirectories: true)

final class Sink: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    let writer: AVAssetWriter
    let clip: AVAssetWriterInput
    let adaptor: AVAssetWriterInputPixelBufferAdaptor
    init(writer: AVAssetWriter, clip: AVAssetWriterInput,
         adaptor: AVAssetWriterInputPixelBufferAdaptor) {
        self.writer = writer; self.clip = clip; self.adaptor = adaptor
    }
    func captureOutput(_ output: AVCaptureOutput,
                       didOutput sampleBuffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        guard writer.status == .writing, clip.isReadyForMoreMediaData else { return }
        if let pb = CMSampleBufferGetImageBuffer(sampleBuffer) {
            adaptor.append(pb, withPresentationTime: CMSampleBufferGetPresentationTimeStamp(sampleBuffer))
        }
    }
}

let session = AVCaptureSession()
session.beginConfiguration()
let input = AVCaptureScreenInput()
input.cropRect = CGRect(x: x, y: y, width: w, height: h)
input.minFrameDuration = CMTime(value: 1, timescale: CMTimeScale(fps.rounded()))
if session.canAddInput(input) { session.addInput(input) }
session.commitConfiguration()

let settings: [String: Any] = [
    AVVideoCodecKey: AVVideoCodecType.h264,
    AVVideoWidthKey: Int(w.rounded()),
    AVVideoHeightKey: Int(h.rounded()),
    AVVideoCompressionPropertiesKey: [
        AVVideoAverageBitRateKey: 8_000_000,
        AVVideoExpectedSourceFrameRateKey: fps,
        AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
    ],
]
let writer = try AVAssetWriter(outputURL: out, fileType: .mov)
let clip = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
clip.expectsMediaDataInRealTime = true
let adaptor = AVAssetWriterInputPixelBufferAdaptor(
    assetWriterInput: clip,
    sourcePixelBufferAttributes: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
guard writer.canAdd(clip) else { fputs("cannot add clip\n", stderr); exit(1) }
writer.add(clip)
let sink = Sink(writer: writer, clip: clip, adaptor: adaptor)

let output = AVCaptureVideoDataOutput()
output.setSampleBufferDelegate(sink, queue: DispatchQueue(label: "frames"))
if session.canAddOutput(output) { session.addOutput(output) }

_ = writer.startWriting()
writer.startSession(atSourceTime: .zero)
session.startRunning()
fputs("recording \(Int(w))x\(Int(h)) @ \(fps)fps for \(Int(secs))s -> \(out.path)\n", stderr)

DispatchQueue.global().asyncAfter(deadline: .now() + secs) {
    session.stopRunning()
    clip.markAsFinished()
    writer.finishWriting {
        if writer.status == .completed {
            fputs("done: \(out.path)\n", stderr)
            exit(0)
        } else {
            fputs("failed: \(writer.error?.localizedDescription ?? "?")\n", stderr)
            exit(1)
        }
    }
}
RunLoop.main.run()
