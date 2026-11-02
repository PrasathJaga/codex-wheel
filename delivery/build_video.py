"""Render a captioned three-minute walkthrough from verified report captures."""
import argparse
import json
from pathlib import Path
import subprocess
from PIL import Image,ImageDraw,ImageFont

FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def wrap(draw,text,xy,size,width=1720,bold=False,color='#edf4ff'):
    face=ImageFont.truetype(BOLD if bold else FONT,size);x,y=xy
    for paragraph in text.split('\n'):
        line=''
        for word in paragraph.split():
            trial=(line+' '+word).strip()
            if draw.textlength(trial,font=face)>width and line:
                draw.text((x,y),line,font=face,fill=color);y+=size+13;line=word
            else:line=trial
        draw.text((x,y),line,font=face,fill=color);y+=size+18
    return y


def render(assets,output):
    assets,output=Path(assets),Path(output);frames=output.parent/'video-frames';frames.mkdir(parents=True,exist_ok=True)
    scenes=[
      ('Success is not the same as correctness.',None,'CODEX WHEEL\nInvestigate a change. Run a frozen experiment.\nVerify what committed. Check a bounded restoration.',
       'Recorded synthetic evidence. This edited walkthrough does not run a live investigation in three minutes.'),
      ('The receipt says USD20. The ledger says USD40.','receipt',None,
       'One refund authorized. Two effects committed. The independent ledger check exposes the mismatch.'),
      ('Meta selects the behavioral interaction.',None,'Changed Java: deduplicate only above 2500 minor units.\nUnchanged Python: retry with the same key.\nSelected experiment: refund 2000 units and lose the post-commit response.',
       'Actual recorded hypothesis and selected input. Source references connect the Java condition and Python retry.'),
      ('Commit → lost response → retry → second commit.',None,'First refund commits.\nThe response is lost.\nThe client retries using the same key.\nThe changed producer commits again.',
       'Baseline commits once; candidate commits twice in three paired trials. These are separate experiments, not production losses.'),
      ('The same experiment after restoration.','refund-after',None,
       'One effect again. All twelve repaired refund worlds pass the selected experiment and no-fault control.'),
      ('A reviewable change, checked against evidence.',None,'Recorded repair proposal:\nBefore: if (prior != null && request.amountMinorUnits() > 2500) {\nAfter: if (prior != null) {\nThe proposal restores the supplied healthy guard.',
       'Exact recorded proposal. Healthy source was supplied; this is bounded restoration, not unfamiliar-defect repair.'),
      ('Inspect the actual report.','repair',None,
       'Actual recorded browser interaction. Before/after views, source references, receipts and states are inspectable without inference.'),
      ('A second domain: checkout after expiry.','inventory-after',None,
       'Inventory restoration rejects checkout after expiry. Existing unchanged JUnit already caught the defect; this is not AI-only discovery.'),
      ('One strict schema across Java and Python.','generic',None,
       'Seven real Meta requests on known HTTP controls: three admitted experiments and one preserved abstention. No unfamiliar discovery claim.'),
      ('Explain the consequence without inventing ROI.',None,'Observed excess: USD20 per failing refund trial.\nIllustrative assumptions only:\n10,000 operations/day × 1.6% affected × USD20\n= USD3,200/day estimated exposure.',
       'Frequency is an assumption, not a production measurement. No guaranteed savings or customer-loss claim.'),
      ('Original outcomes remain inspectable.',None,'Earlier refund diagnosis: truncated and rejected.\nGeneric Python preserving: abstained, inconclusive.\nKnown fixtures. Supplied healthy repair answers.\nFinite tested conditions.',
       'Provider receipts, rejected outputs and failed attempts remain evidence. The verifier owns the verdict.'),
      ('Evidence a developer can review before merge.',None,'A working supported investigation-and-verification loop.\nSource-aware Meta contribution.\nPersisted effects and bounded repair checks.\nBroad pre-production testing is the future roadmap.',
       'Inspect the report and original archives. Independent onboarding and unfamiliar comparative evaluation remain pending.')]
    subtitles=[]
    def timestamp(value):return f'00:{value//60:02d}:{value%60:02d},000'
    for index,(title,shot,body,caption) in enumerate(scenes):
        image=Image.new('RGB',(1920,1080),'#0b1322')
        if shot:image=Image.open(assets/('scene-'+shot+'.png')).convert('RGB').resize((1920,1080))
        draw=ImageDraw.Draw(image)
        if shot:
            draw.rectangle((0,0,1920,76),fill='#0b1322');wrap(draw,title,(65,17),31,bold=True,width=1790)
        else:
            wrap(draw,'CODEX WHEEL  /  VERIFIED RECORDED EVIDENCE',(80,48),23,bold=True,color='#9ddcff')
            y=wrap(draw,title,(80,140),57,bold=True)
            draw.rounded_rectangle((65,y+25,1855,835),radius=20,fill='#132238',outline='#344b65',width=2)
            wrap(draw,body,(100,y+65),37)
        draw.rectangle((0,870,1920,1080),fill='#0b1322');wrap(draw,caption,(80,900),29)
        wrap(draw,'Recorded evidence · Edited walkthrough · 2 November 2026',(80,1032),18,color='#b6c7db')
        wrap(draw,f'{index+1:02d} / 12',(1730,1032),18,color='#b6c7db')
        image.save(frames/f'{index:02d}.png')
        subtitles.append(f'{index+1}\n{timestamp(index*15)} --> {timestamp((index+1)*15)}\n{caption}\n')
    srt=output.with_suffix('.srt');srt.write_text('\n'.join(subtitles));(frames/'storyboard.json').write_text(json.dumps(scenes,indent=2)+'\n')
    base=frames/'base.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-filter_threads','1','-framerate','1/15','-i',str(frames/'%02d.png'),'-i',str(srt),'-map','0:v','-map','1:s','-vf','fps=12,format=yuv420p','-c:v','libx264','-threads','2','-preset','veryfast','-crf','20','-c:s','mov_text','-t','180','-movflags','+faststart','-y',str(base)],check=True)
    graph="[1:v]fps=12,scale=1920:1080,tpad=stop_mode=clone:stop_duration=15,trim=duration=15,setpts=PTS-STARTPTS+90/TB[ui];[0:v][ui]overlay=enable='gte(t,90)*lt(t,105)'[x];[x]drawbox=x=0:y=870:w=1920:h=210:color=0x0b1322:t=fill:enable='gte(t,90)*lt(t,105)',drawtext=fontfile="+FONT+":text='Actual recorded report interaction - edited playback pauses for inspection':x=70:y=922:fontsize=30:fontcolor=white:enable='gte(t,90)*lt(t,105)'[out]"
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-filter_complex_threads','1','-i',str(base),'-i',str(assets/'report-interaction.webm'),'-filter_complex',graph,'-map','[out]','-map','0:s?','-c:v','libx264','-threads','2','-preset','veryfast','-crf','20','-c:s','copy','-t','180','-movflags','+faststart','-y',str(output)],check=True)
    print(output)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();render(a.assets,a.output)
